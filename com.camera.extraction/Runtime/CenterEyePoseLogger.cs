using System;
using System.IO;
using UnityEngine;

namespace CameraExtraction
{
	public class CenterEyePoseLogger : MonoBehaviour
	{
		public Camera targetCamera;
		public int frameInterval;
		public float poseIntervalSeconds = 1.0f;
		public float screenshotIntervalSeconds = 1.0f;
		public bool captureScreenshot = true;
		public string customScreenshotPath = "";
			public string customPosesPath = "";

	private string logDir;
	private string screenshotDir;
	private string logPath;
	private int frameCount;
	private RenderTexture renderTexture;
		private int screenshotWidth;
		private int screenshotHeight;
		private CameraExtractionConfig config;

		[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
		private static void AutoAttachToMainCamera()
		{
			if (FindObjectOfType<CenterEyePoseLogger>() != null) return;
			GameObject mainCameraObj = GameObject.FindGameObjectWithTag("MainCamera");
			if (mainCameraObj == null) { Debug.LogWarning("[CenterEyePoseLogger] No MainCamera found"); return; }
			var logger = mainCameraObj.AddComponent<CenterEyePoseLogger>();
			logger.targetCamera = mainCameraObj.GetComponent<Camera>();
			Debug.Log($"[CenterEyePoseLogger] Auto-attached to MainCamera: {mainCameraObj.name}");
		}

		private bool initialized;

		void Awake()
		{
			// load and apply config (no heavy initialization until camera is assigned)
			config = CameraExtractionConfig.Load();
			frameInterval = config.frameInterval;
			poseIntervalSeconds = config.poseIntervalSeconds;
			screenshotIntervalSeconds = config.screenshotIntervalSeconds;
			captureScreenshot = config.captureScreenshot;
			ApplyCliOverridesFromArgs();
			initialized = false;
		}

		void Start()
		{
			// Attempt initialization if camera already assigned
			if (targetCamera == null) targetCamera = Camera.main;
			InitializeOutputsIfNeeded(false);
		}

		void OnDestroy()
		{
			if (renderTexture != null) { renderTexture.Release(); DestroyImmediate(renderTexture); }
		}

	void Update()
	{
		if (targetCamera == null) return;
		// Note: Transform validation moved to TriggerScreenshotAndPose to avoid skipping frame count
		ReorientToMainIfEnabled();
		InitializeOutputsIfNeeded(false);
		frameCount++;
		
		// Screenshot and pose logging is now triggered globally by MultiCameraExtractor
		// This ensures all cameras capture at the same moment with synchronized timestamps
	}

	/// <summary>
	/// Triggered externally by MultiCameraExtractor for synchronized screenshot and pose logging
	/// </summary>
	/// <returns>True if successful, false if skipped due to invalid state</returns>
	public bool TriggerScreenshotAndPose()
	{
		if (targetCamera == null) 
		{
			Debug.LogWarning("[CenterEyePoseLogger] TriggerScreenshotAndPose failed: targetCamera is null");
			return false;
		}
		
		if (!captureScreenshot)
		{
			return false;  // Screenshot capture is disabled
		}
		
		if (!IsTransformValid(targetCamera.transform))
		{
			Debug.LogWarning($"[CenterEyePoseLogger] TriggerScreenshotAndPose skipped for {targetCamera.gameObject.name}: invalid transform");
			return false;
		}
		
		try
		{
			// Capture screenshot first
			string screenshotName = CaptureScreenshot(frameCount, null);
			
			if (string.IsNullOrEmpty(screenshotName))
			{
				Debug.LogWarning($"[CenterEyePoseLogger] Screenshot capture failed for {targetCamera.gameObject.name}");
				return false;
			}
			
			// Then log pose data along with screenshot
			Vector3 p = targetCamera.transform.position; 
			Quaternion q = targetCamera.transform.rotation;
			string timeUtc = DateTime.UtcNow.ToString("o");
			
			File.AppendAllText(logPath, string.Format("{0},{1},{2:F6},{3:F6},{4:F6},{5:F6},{6:F6},{7:F6},{8:F6},{9}\n", 
				frameCount, timeUtc, p.x, p.y, p.z, q.x, q.y, q.z, q.w, screenshotName));
			
			return true;
		}
		catch (Exception e)
		{
			Debug.LogError($"[CenterEyePoseLogger] TriggerScreenshotAndPose exception for {targetCamera.gameObject.name}: {e.Message}");
			return false;
		}
	}

	/// <summary>
	/// External trigger with a shared timestamp to guarantee all screenshots go into the same timestamp folder
	/// </summary>
	public bool TriggerScreenshotAndPose(string sharedTimestamp)
	{
		return TriggerScreenshotAndPose(sharedTimestamp, "", "");
	}

	/// <summary>
	/// External trigger with agent ID and timestamp for custom filename formatting
	/// Records screenshot, pose, and intrinsics
	/// </summary>
	public bool TriggerScreenshotAndPose(string sharedTimestamp, string agentId, string agentTimestamp)
	{
		if (targetCamera == null) 
		{
			Debug.LogWarning("[CenterEyePoseLogger] TriggerScreenshotAndPose(sharedTimestamp, agentId, agentTimestamp) failed: targetCamera is null");
			return false;
		}
		if (!captureScreenshot) return false;
		if (!IsTransformValid(targetCamera.transform))
		{
			Debug.LogWarning($"[CenterEyePoseLogger] TriggerScreenshotAndPose(sharedTimestamp, agentId, agentTimestamp) skipped for {targetCamera.gameObject.name}: invalid transform");
			return false;
		}
		try
		{
			// 1. Capture screenshot
			string screenshotName = CaptureScreenshot(frameCount, sharedTimestamp, agentId, agentTimestamp);
			if (string.IsNullOrEmpty(screenshotName)) return false;
			
			// 2. Log pose data
			Vector3 p = targetCamera.transform.position; 
			Quaternion q = targetCamera.transform.rotation;
			string timeUtc = DateTime.UtcNow.ToString("o");
			File.AppendAllText(logPath, string.Format("{0},{1},{2:F6},{3:F6},{4:F6},{5:F6},{6:F6},{7:F6},{8:F6},{9}\n", 
				frameCount, timeUtc, p.x, p.y, p.z, q.x, q.y, q.z, q.w, screenshotName));
			
			// 3. Extract and save camera intrinsics (with agent ID and timestamp in filename)
			var intrinsics = targetCamera.gameObject.GetComponent<CameraIntrinsicsFromFOV>();
			if (intrinsics != null)
			{
				intrinsics.ExtractIntrinsicsNowWithAgentInfo(agentId, agentTimestamp);
			}
			
			return true;
		}
		catch (Exception e)
		{
			Debug.LogError($"[CenterEyePoseLogger] TriggerScreenshotAndPose(sharedTimestamp, agentId, agentTimestamp) exception for {targetCamera.gameObject.name}: {e.Message}");
			return false;
		}
	}

	public void ExtractPoseNow()
	{
		if (targetCamera == null) return;
		Vector3 p = targetCamera.transform.position; Quaternion q = targetCamera.transform.rotation;
		string timeUtc = DateTime.UtcNow.ToString("o");
		File.AppendAllText(logPath, string.Format("{0},{1},{2:F6},{3:F6},{4:F6},{5:F6},{6:F6},{7:F6},{8:F6},\n", frameCount, timeUtc, p.x, p.y, p.z, q.x, q.y, q.z, q.w));
	}

	public string CaptureScreenshotNow(int frame)
	{
		return CaptureScreenshot(frame);
	}

	string CaptureScreenshot(int frame)
	{
		try
		{
			if (!IsTransformValid(targetCamera.transform)) return "";
			ReorientToMainIfEnabled();
			// save current target camera texture
			RenderTexture originalRT = targetCamera.targetTexture;
			// redirect set target camera texture to render texture
			targetCamera.targetTexture = renderTexture;
			// render to render texture
			targetCamera.Render();
			// restore original target camera texture
			targetCamera.targetTexture = originalRT;
			// read pixels from render texture
			Texture2D screenshot = new Texture2D(screenshotWidth, screenshotHeight, TextureFormat.RGB24, false);
			RenderTexture.active = renderTexture; screenshot.ReadPixels(new Rect(0, 0, screenshotWidth, screenshotHeight), 0, 0); screenshot.Apply(); RenderTexture.active = null;
			byte[] png = screenshot.EncodeToPNG();
			
			var projectName = CameraExtractionConfig.GetProjectName(); 
			string camNameSafe = SanitizeName(targetCamera.gameObject.name + "__" + targetCamera.gameObject.GetInstanceID());
			
			// Determine output directory and filename based on organization mode
			string outputDir;
			string filename;
			string relativePathForCSV;
			
			if (config.GetScreenshotOrganizationMode() == ScreenshotOrganizationMode.ByTimestamp)
			{
				// ByTimestamp mode: all cameras in same timestamp folder (per second)
				// Use second-level precision so all screenshots in same second share one folder
				string timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
				
				// Get base screenshots path (one level up from camera-specific folder)
				string baseScreenshotsPath = Path.GetFullPath(Path.Combine(screenshotDir, ".."));
				string timestampFolder = Path.Combine(baseScreenshotsPath, timestamp);
				outputDir = timestampFolder;
				Directory.CreateDirectory(outputDir);
				
				// Include camera name in filename to distinguish different cameras
				filename = $"{projectName}_{camNameSafe}_frame_{frame:D6}.png";
				relativePathForCSV = Path.Combine(timestamp, filename);
			}
			else
			{
				// ByCamera mode: each camera has its own folder (default)
				outputDir = screenshotDir;
				filename = $"{projectName}_{camNameSafe}_screenshot_frame_{frame:D6}.png";
				relativePathForCSV = filename;
			}
			
			string filepath = Path.Combine(outputDir, filename);
			File.WriteAllBytes(filepath, png); 
			DestroyImmediate(screenshot);
			Debug.Log($"[CenterEyePoseLogger] Screenshot saved: {filepath}");
			return relativePathForCSV;
		}
		catch (Exception e) { Debug.LogError($"[CenterEyePoseLogger] Failed to capture screenshot: {e}"); return ""; }
	}

	// Overload with shared timestamp to avoid per-camera second-boundary splits
	string CaptureScreenshot(int frame, string sharedTimestamp)
	{
		return CaptureScreenshot(frame, sharedTimestamp, "", "");
	}

	// Overload with agent ID and timestamp for custom filename formatting
	string CaptureScreenshot(int frame, string sharedTimestamp, string agentId, string agentTimestamp)
	{
		try
		{
			if (!IsTransformValid(targetCamera.transform)) return "";
			ReorientToMainIfEnabled();
			RenderTexture originalRT = targetCamera.targetTexture;
			targetCamera.targetTexture = renderTexture;
			targetCamera.Render();
			targetCamera.targetTexture = originalRT;
			Texture2D screenshot = new Texture2D(screenshotWidth, screenshotHeight, TextureFormat.RGB24, false);
			RenderTexture.active = renderTexture; screenshot.ReadPixels(new Rect(0, 0, screenshotWidth, screenshotHeight), 0, 0); screenshot.Apply(); RenderTexture.active = null;
			byte[] png = screenshot.EncodeToPNG();
			var projectName = CameraExtractionConfig.GetProjectName(); 
			string camNameSafe = SanitizeName(targetCamera.gameObject.name + "__" + targetCamera.gameObject.GetInstanceID());
			string outputDir;
			string filename;
			string relativePathForCSV;
			
			// Build filename with agent ID and timestamp if provided
			string filenamePrefix = "";
			if (!string.IsNullOrEmpty(agentId))
			{
				string safeAgentId = SanitizeName(agentId);
				string timestampPart = !string.IsNullOrEmpty(agentTimestamp) ? agentTimestamp : DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
				filenamePrefix = $"{safeAgentId}_{timestampPart}_";
			}
			
			if (config.GetScreenshotOrganizationMode() == ScreenshotOrganizationMode.ByTimestamp)
			{
				string timestamp = string.IsNullOrEmpty(sharedTimestamp) ? DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture) : sharedTimestamp;
				string baseScreenshotsPath = Path.GetFullPath(Path.Combine(screenshotDir, ".."));
				string timestampFolder = Path.Combine(baseScreenshotsPath, timestamp);
				outputDir = timestampFolder;
				Directory.CreateDirectory(outputDir);
				filename = $"{filenamePrefix}{projectName}_{camNameSafe}_frame_{frame:D6}.png";
				relativePathForCSV = Path.Combine(timestamp, filename);
			}
			else
			{
				outputDir = screenshotDir;
				filename = $"{filenamePrefix}{projectName}_{camNameSafe}_screenshot_frame_{frame:D6}.png";
				relativePathForCSV = filename;
			}
			string filepath = Path.Combine(outputDir, filename);
			File.WriteAllBytes(filepath, png);
			DestroyImmediate(screenshot);
			Debug.Log($"[CenterEyePoseLogger] Screenshot saved: {filepath}");
			return relativePathForCSV;
		}
		catch (Exception e) { Debug.LogError($"[CenterEyePoseLogger] Failed to capture screenshot(sharedTimestamp, agentId, agentTimestamp): {e}"); return ""; }
	}

		private void ApplyCliOverridesFromArgs()
		{
			try
			{
				foreach (string arg in Environment.GetCommandLineArgs())
				{
					if (arg.StartsWith("--screenshotDir=")) customScreenshotPath = arg.Substring("--screenshotDir=".Length).Trim('"');
					else if (arg.StartsWith("--frameInterval=") && int.TryParse(arg.Substring("--frameInterval=".Length), out int n)) frameInterval = Mathf.Max(1, n);
					else if (arg.StartsWith("--poseInterval=") && float.TryParse(arg.Substring("--poseInterval=".Length), out float p)) poseIntervalSeconds = Mathf.Max(0.1f, p);
					else if (arg.StartsWith("--screenshotInterval=") && float.TryParse(arg.Substring("--screenshotInterval=".Length), out float f)) screenshotIntervalSeconds = Mathf.Max(0.1f, f);
					else if (arg.StartsWith("--captureScreenshot=")) { string v = arg.Substring("--captureScreenshot=".Length); captureScreenshot = v == "1" || v.ToLowerInvariant() == "true"; }
				}
			}
			catch (Exception e) { Debug.LogWarning($"[CenterEyePoseLogger] CLI parse failed: {e}"); }
		}

		private void InitializeOutputsIfNeeded(bool forceReinit)
		{
			if (targetCamera == null) return;
			if (initialized && !forceReinit) return;
			string cameraName = targetCamera.gameObject.name;
			string uniqueCameraId = cameraName + "__" + targetCamera.gameObject.GetInstanceID();
			logDir = string.IsNullOrEmpty(customPosesPath) ? config.GetPosesPathForCamera(uniqueCameraId) : customPosesPath;
			screenshotDir = string.IsNullOrEmpty(customScreenshotPath) ? config.GetScreenshotsPathForCamera(uniqueCameraId) : customScreenshotPath;
			
		Directory.CreateDirectory(logDir);
		Directory.CreateDirectory(screenshotDir);
		var projectName = CameraExtractionConfig.GetProjectName();
		string camNameSafe = SanitizeName(targetCamera.gameObject.name + "__" + targetCamera.gameObject.GetInstanceID());
		// Use fixed filename without timestamp so all poses go to the same file
		logPath = Path.Combine(logDir, $"{projectName}_{camNameSafe}_hmd_pose.csv");
		// Only write header if file doesn't exist
		if (!File.Exists(logPath))
		{
			File.WriteAllText(logPath, "frameCount,timeUTC,posX,posY,posZ,rotX,rotY,rotZ,rotW,screenshotPath\n");
		}
			// Determine screenshot resolution: prefer configured size if provided
			screenshotWidth = (config.screenshotWidth > 0) ? config.screenshotWidth : targetCamera.pixelWidth;
			screenshotHeight = (config.screenshotHeight > 0) ? config.screenshotHeight : targetCamera.pixelHeight;
			if (captureScreenshot)
			{
				if (renderTexture != null) { renderTexture.Release(); DestroyImmediate(renderTexture); }
				renderTexture = new RenderTexture(screenshotWidth, screenshotHeight, 24);
				renderTexture.Create();
			}
			initialized = true;
			Debug.Log($"[CenterEyePoseLogger] Initialized for camera '{cameraName}'. Poses={logDir}, Screenshots={screenshotDir}");
		}

	private void ReorientToMainIfEnabled()
	{
		if (config == null || !config.reorientCameras) return;
		// Skip if this is the main camera itself
		if (targetCamera != null && targetCamera.gameObject.CompareTag(config.targetCameraTag)) return;
		var mainObj = GameObject.FindGameObjectWithTag(config.targetCameraTag);
		if (mainObj == null) return;
		var mainCam = mainObj.GetComponent<Camera>();
		if (mainCam == null) return;
		
		// Validate transforms before reorientation
		if (!IsTransformValid(mainCam.transform) || !IsTransformValid(targetCamera.transform))
		{
			return;
		}
		
		// Cast ray from main camera to find look-at target (limit to 100 meters)
		Ray ray = new Ray(mainCam.transform.position, mainCam.transform.forward);
		RaycastHit hit;
		float maxRayDistance = 100f;
		
		if (Physics.Raycast(ray, out hit, maxRayDistance))
		{
			// Validate hit point and direction before LookAt
			Vector3 direction = hit.point - targetCamera.transform.position;
			float distanceSqr = direction.sqrMagnitude;
			// targetCamera.transform.LookAt(hit.point, Vector3.up);
			
			// Skip if hit point is too close (<0.01m) or too far (>1000m) or invalid
			if (distanceSqr > 0.0001f && distanceSqr < 1000000f && IsFinite(direction))
			{
				// Hit something: make this camera look at the hit point with stable up vector
				targetCamera.transform.LookAt(hit.point, Vector3.up);
			}
			else
			{
				// Invalid hit point: fallback to copying rotation
				targetCamera.transform.rotation = mainCam.transform.rotation;
			}
		}
		else
		{
			// No hit: fallback to copying main camera's rotation
			targetCamera.transform.rotation = mainCam.transform.rotation;
		}
	}

		private static bool IsFinite(Vector3 v)
		{
			return float.IsFinite(v.x) && float.IsFinite(v.y) && float.IsFinite(v.z);
		}

		private static bool IsTransformValid(Transform t)
		{
			if (t == null) return false;
			var p = t.position;
			var s = t.lossyScale;
			if (!IsFinite(p) || !IsFinite(s)) return false;
			if (p.sqrMagnitude > 1e12f) return false;
			if (s.x == 0f || s.y == 0f || s.z == 0f) return false;
			if (Mathf.Abs(s.x) > 1e6f || Mathf.Abs(s.y) > 1e6f || Mathf.Abs(s.z) > 1e6f) return false;
			return true;
		}

		public void Configure(Camera cam, string posesDir, string screenshotsDir, int interval, float poseInterval, float screenshotInterval, bool capture)
		{
			targetCamera = cam;
			customPosesPath = posesDir;
			customScreenshotPath = screenshotsDir;
			frameInterval = Mathf.Max(1, interval);
			poseIntervalSeconds = Mathf.Max(0.1f, poseInterval);
			screenshotIntervalSeconds = Mathf.Max(0.1f, screenshotInterval);
			captureScreenshot = capture;
			InitializeOutputsIfNeeded(true);
		}

		private static string SanitizeName(string name)
		{
			if (string.IsNullOrEmpty(name)) return "Camera";
			foreach (char c in System.IO.Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
			return name;
		}
	}
}