"""
CLIP Feature Extraction Module

Extracts visual features from images using CLIP (Contrastive Language-Image Pre-training).
These features are used for visual similarity matching in the shared memory system.
"""
import os
import numpy as np
from pathlib import Path
from typing import Optional, Union, List
import base64

# Global model instances (avoid repeated loading)
_clip_model = None
_clip_processor = None
_clip_device = None


def get_clip_model():
    """
    Get or initialize CLIP model.
    
    Uses transformers library with CLIP ViT-B/32 model (512-dim output).
    Falls back to fake model if DISABLE_CLIP env var is set or loading fails.
    """
    global _clip_model, _clip_processor, _clip_device
    
    if _clip_model is None:
        if os.getenv("DISABLE_CLIP"):
            print("[CLIP] CLIP disabled via environment variable, using fake model")
            _clip_model = _FakeCLIPModel()
            _clip_processor = None
            _clip_device = "cpu"
        else:
            try:
                import torch
                from transformers import CLIPProcessor, CLIPModel
                
                # Use CLIP ViT-B/32 (512-dim features)
                model_name = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
                print(f"[CLIP] Loading CLIP model: {model_name}")
                
                _clip_model = CLIPModel.from_pretrained(model_name)
                _clip_processor = CLIPProcessor.from_pretrained(model_name)
                
                # Use GPU if available
                _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
                _clip_model = _clip_model.to(_clip_device)
                _clip_model.eval()
                
                print(f"[CLIP] Model loaded successfully on {_clip_device}")
                
            except Exception as e:
                print(f"[CLIP] Failed to load CLIP model: {e}")
                print("[CLIP] Falling back to fake model")
                _clip_model = _FakeCLIPModel()
                _clip_processor = None
                _clip_device = "cpu"
    
    return _clip_model, _clip_processor, _clip_device


class _FakeCLIPModel:
    """Fake CLIP model for testing when real model is unavailable."""
    
    def __init__(self, dimension: int = 512):
        self.dimension = dimension
    
    def get_image_features(self, **kwargs):
        """Return deterministic fake features based on pixel values."""
        import torch
        pixel_values = kwargs.get("pixel_values")
        if pixel_values is not None:
            # Use pixel values to generate deterministic features
            batch_size = pixel_values.shape[0]
            # Create hash-based features
            features = []
            for i in range(batch_size):
                # Use mean of pixel values as seed for reproducibility
                seed = int(abs(pixel_values[i].mean().item()) * 1e6) % (2**32)
                rng = np.random.default_rng(seed)
                vec = rng.standard_normal(self.dimension).astype(np.float32)
                vec = vec / (np.linalg.norm(vec) + 1e-12)
                features.append(vec)
            return torch.tensor(np.stack(features))
        return torch.zeros(1, self.dimension)
    
    def to(self, device):
        return self
    
    def eval(self):
        return self


def extract_visual_features(
    image_path: str,
    normalize: bool = True
) -> Optional[np.ndarray]:
    """
    Extract visual features from an image using CLIP.
    
    Args:
        image_path: Path to the image file
        normalize: Whether to L2-normalize the features (default True)
    
    Returns:
        Feature vector (512 dimensions by default) or None if extraction fails
    """
    model, processor, device = get_clip_model()
    
    try:
        # Load image
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        
        if processor is not None:
            # Real CLIP model
            import torch
            inputs = processor(images=image, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                features = model.get_image_features(**inputs)
            
            features = features.cpu().numpy().squeeze()
        else:
            # Fake model - pass pixel values directly
            import torch
            # Simple preprocessing for fake model
            img_array = np.array(image.resize((224, 224))) / 255.0
            pixel_values = torch.tensor(img_array).permute(2, 0, 1).unsqueeze(0).float()
            features = model.get_image_features(pixel_values=pixel_values)
            features = features.numpy().squeeze()
        
        # Normalize
        if normalize:
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm
        
        return features.astype(np.float32)
        
    except Exception as e:
        print(f"[CLIP] Error extracting features from {image_path}: {e}")
        return None


def extract_visual_features_batch(
    image_paths: List[str],
    normalize: bool = True
) -> List[Optional[np.ndarray]]:
    """
    Extract visual features from multiple images in batch.
    
    Args:
        image_paths: List of image file paths
        normalize: Whether to L2-normalize the features
    
    Returns:
        List of feature vectors (None for failed extractions)
    """
    model, processor, device = get_clip_model()
    results = []
    
    try:
        from PIL import Image
        import torch
        
        # Load all valid images
        images = []
        valid_indices = []
        for i, path in enumerate(image_paths):
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
                valid_indices.append(i)
            except Exception as e:
                print(f"[CLIP] Failed to load image {path}: {e}")
        
        if not images:
            return [None] * len(image_paths)
        
        if processor is not None:
            # Real CLIP model - batch processing
            inputs = processor(images=images, return_tensors="pt", padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                features = model.get_image_features(**inputs)
            
            features = features.cpu().numpy()
        else:
            # Fake model
            all_features = []
            for img in images:
                img_array = np.array(img.resize((224, 224))) / 255.0
                pixel_values = torch.tensor(img_array).permute(2, 0, 1).unsqueeze(0).float()
                feat = model.get_image_features(pixel_values=pixel_values)
                all_features.append(feat.numpy().squeeze())
            features = np.stack(all_features)
        
        # Normalize
        if normalize:
            norms = np.linalg.norm(features, axis=1, keepdims=True)
            norms = np.where(norms > 0, norms, 1)
            features = features / norms
        
        # Map back to original indices
        results = [None] * len(image_paths)
        for i, idx in enumerate(valid_indices):
            results[idx] = features[i].astype(np.float32)
        
        return results
        
    except Exception as e:
        print(f"[CLIP] Batch extraction error: {e}")
        return [None] * len(image_paths)


def compute_visual_similarity(
    features1: np.ndarray,
    features2: np.ndarray
) -> float:
    """
    Compute cosine similarity between two visual feature vectors.
    
    Args:
        features1: First feature vector
        features2: Second feature vector
    
    Returns:
        Cosine similarity (0 to 1 for normalized vectors)
    """
    # Ensure vectors are normalized
    norm1 = np.linalg.norm(features1)
    norm2 = np.linalg.norm(features2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = np.dot(features1, features2) / (norm1 * norm2)
    return float(similarity)


def get_clip_dimension() -> int:
    """Get the dimension of CLIP features."""
    model, _, _ = get_clip_model()
    if isinstance(model, _FakeCLIPModel):
        return model.dimension
    # Default CLIP ViT-B/32 dimension
    return 512


if __name__ == "__main__":
    # Test CLIP features
    print("Testing CLIP feature extraction...")
    
    # Test with a sample image (if available)
    test_image = "test_image.png"
    
    if os.path.exists(test_image):
        features = extract_visual_features(test_image)
        if features is not None:
            print(f"Feature shape: {features.shape}")
            print(f"Feature norm: {np.linalg.norm(features):.4f}")
            print(f"First 10 values: {features[:10]}")
        else:
            print("Feature extraction failed")
    else:
        print(f"Test image not found: {test_image}")
        print("Testing with fake model...")
        
        # Force fake model for testing
        os.environ["DISABLE_CLIP"] = "1"
        
        # Create a dummy test
        from PIL import Image
        dummy_img = Image.new("RGB", (224, 224), color="red")
        dummy_path = "test_dummy.png"
        dummy_img.save(dummy_path)
        
        features = extract_visual_features(dummy_path)
        if features is not None:
            print(f"Feature shape: {features.shape}")
            print(f"Feature norm: {np.linalg.norm(features):.4f}")
        
        # Clean up
        os.remove(dummy_path)
    
    print(f"\nCLIP feature dimension: {get_clip_dimension()}")

