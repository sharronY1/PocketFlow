using System;
using System.IO;
using UnityEngine;

namespace CameraExtraction
{
    public enum ScreenshotOrganizationMode
    {
        ByCamera,      // Organize by camera name (default)
        ByTimestamp    // Organize by timestamp (all cameras in same time folder)
    }

    [System.Serializable]
    public class CameraExtractionConfig
    {
        [Header("Output Settings")]
        public string outputBasePath = "";
        public bool useProjectSubfolder = true;
        
        [Header("Recording Settings")]
        public int frameInterval = 30;
        public float screenshotIntervalSeconds = 1.0f;
        public bool captureScreenshot = true;
        public bool autoScreenshotEnabled = true;  // If false, screenshots are only triggered by Agent requests
        public string agentControlRequestDir = "";  // Directory to watch for Agent screenshot requests
        public int durationSeconds = 10;
		public int maxTrackedObjects = 2;
        
        [Header("Occlusion Filtering")]
        public bool filterByWallOcclusion = true;      // Enable wall-occlusion filtering between Main Camera and candidates
        public string wallNameKeywords = "boundary,wall,barrier,reset";  // Comma-separated keywords to identify wall/boundary objects by name
        public float visibilitySampleVerticalOffset = 0.2f; // Vertical offset for multi-sample visibility checks
        
        [Header("Camera Settings")]
        public bool autoAttachToMainCamera = true;
        public string targetCameraTag = "MainCamera";
        public bool reorientCameras = true;
        public bool useUniformFOV = false;  // Set all cameras to the same FOV
        public float uniformFOV = 60.0f;    // Uniform FOV in degrees (default: 60)
        public int screenshotWidth = 0;     // 0 = use camera pixelWidth
        public int screenshotHeight = 0;    // 0 = use camera pixelHeight
        
        [Header("File Settings")]
        public string screenshotSubfolder = "screenshots";
        public string posesSubfolder = "poses";
        public string intrinsicsSubfolder = "intrinsics";
        public string screenshotOrganizationMode = "ByCamera"; // "ByCamera" or "ByTimestamp"
        
        public static string GetConfigPath()
        {
            // fallback to project config file
            string projectRoot = Path.GetDirectoryName(Application.dataPath);
            string projectConfigPath = Path.Combine(projectRoot, "camera_extraction_config.json");
            
            if (File.Exists(projectConfigPath))
            {
                Debug.Log($"[CameraExtraction] Using project config: {projectConfigPath}");
                return projectConfigPath;
            }
            
            // fallback to package config file
            string packageConfigPath = GetPackageConfigPath();
            if (!string.IsNullOrEmpty(packageConfigPath) && File.Exists(packageConfigPath))
            {
                Debug.Log($"[CameraExtraction] Using package config: {packageConfigPath}");
                return packageConfigPath;
            }
            
            // fallback to persistentDataPath
            string fallbackPath = Path.Combine(Application.persistentDataPath, "camera_extraction_config.json");
            Debug.Log($"[CameraExtraction] Using fallback config: {fallbackPath}");
            return fallbackPath;
        }

        private static string GetPackageConfigPath()
        {
            // get package config file path
            // Packages/com.camera.extraction/
            string[] possiblePaths = {
                "Packages/com.camera.extraction/camera_extraction_config.json",
                "Assets/Plugins/com.camera.extraction/camera_extraction_config.json"
            };
            
            foreach (string relativePath in possiblePaths)
            {
                string fullPath = Path.Combine(Application.dataPath, "..", relativePath);
                if (File.Exists(fullPath))
                    return fullPath;
            }
            
            return null;
        }
        
        // load config
        public static CameraExtractionConfig Load()
        {
            string configPath = GetConfigPath();
            
            try
            {
                if (File.Exists(configPath))
                {
                    string json = File.ReadAllText(configPath);
                    var config = JsonUtility.FromJson<CameraExtractionConfig>(json);
                    Debug.Log($"[CameraExtraction] Loaded config from: {configPath}");
                    return config;
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[CameraExtraction] Failed to load config: {e.Message}");
            }
            
            // return default config
            var defaultConfig = new CameraExtractionConfig();
            Debug.Log("[CameraExtraction] Using default config");
            return defaultConfig;
        }
        
        // save config
        public void Save()
        {
            string configPath = GetConfigPath();
            
            try
            {
                string json = JsonUtility.ToJson(this, true);
                File.WriteAllText(configPath, json);
                Debug.Log($"[CameraExtraction] Saved config to: {configPath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[CameraExtraction] Failed to save config: {e.Message}");
            }
        }
        
        // get final output directory
        public string GetOutputDirectory()
        {
            string basePath = string.IsNullOrEmpty(outputBasePath) ? 
                Application.persistentDataPath : outputBasePath;
                
            if (useProjectSubfolder)
            {
                string projectName = GetProjectName();
                return Path.Combine(basePath, projectName);
            }
            
            return Path.Combine(basePath);
        }
        
        // get specific subdirectories
		public string GetScreenshotsPath() 
		{
			// If not using project subfolder, save directly to outputBasePath
			if (!useProjectSubfolder)
			{
				string basePath = string.IsNullOrEmpty(outputBasePath) ? 
					Application.persistentDataPath : outputBasePath;
				return Path.Combine(basePath, screenshotSubfolder);
			}
			return Path.Combine(GetOutputDirectory(), EnsurePrefixedWithProject(screenshotSubfolder));
		}
		public string GetPosesPath() 
		{
			if (!useProjectSubfolder)
			{
				string basePath = string.IsNullOrEmpty(outputBasePath) ? 
					Application.persistentDataPath : outputBasePath;
				return Path.Combine(basePath, posesSubfolder);
			}
			return Path.Combine(GetOutputDirectory(), EnsurePrefixedWithProject(posesSubfolder));
		}
		public string GetIntrinsicsPath() 
		{
			if (!useProjectSubfolder)
			{
				string basePath = string.IsNullOrEmpty(outputBasePath) ? 
					Application.persistentDataPath : outputBasePath;
				return Path.Combine(basePath, intrinsicsSubfolder);
			}
			return Path.Combine(GetOutputDirectory(), EnsurePrefixedWithProject(intrinsicsSubfolder));
		}

		// Per-camera subdirectories
		public string GetScreenshotsPathForCamera(string cameraName)
		{
			return Path.Combine(GetScreenshotsPath(), SanitizeName(cameraName));
		}

		public string GetPosesPathForCamera(string cameraName)
		{
			return Path.Combine(GetPosesPath(), SanitizeName(cameraName));
		}

		public string GetIntrinsicsPathForCamera(string cameraName)
		{
			return Path.Combine(GetIntrinsicsPath(), SanitizeName(cameraName));
		}

		// Get screenshot organization mode
		public ScreenshotOrganizationMode GetScreenshotOrganizationMode()
		{
			if (string.IsNullOrEmpty(screenshotOrganizationMode)) return ScreenshotOrganizationMode.ByCamera;
			
			if (screenshotOrganizationMode.Equals("ByTimestamp", StringComparison.OrdinalIgnoreCase))
				return ScreenshotOrganizationMode.ByTimestamp;
			
			return ScreenshotOrganizationMode.ByCamera;
		}

        public static string GetProjectName()
        {
			// Prefer the Unity project folder name to distinguish cloned projects
			string folderName = Path.GetFileName(Path.GetDirectoryName(Application.dataPath));
			return folderName;
        }

        private static string EnsurePrefixedWithProject(string subfolder)
        {
            string projectName = GetProjectName();
            if (string.IsNullOrEmpty(subfolder)) return projectName;
            string expectedPrefix = projectName + "_";
            return subfolder.StartsWith(expectedPrefix, StringComparison.OrdinalIgnoreCase) ? subfolder : expectedPrefix + subfolder;
        }

		private static string SanitizeName(string name)
		{
			if (string.IsNullOrEmpty(name)) return "Camera";
			foreach (char c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
			return name;
		}
    }
}