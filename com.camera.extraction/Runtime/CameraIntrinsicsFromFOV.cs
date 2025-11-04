using UnityEngine;
using System.IO;
using System.Globalization;

namespace CameraExtraction
{
	public class CameraIntrinsicsFromFOV : MonoBehaviour
	{
		public Camera targetCamera;
		public bool saveToFile = true;
		[SerializeField] private int w, h; [SerializeField] private float fovDeg, fx, fy, cx, cy;
			private CameraExtractionConfig config;
			public string customIntrinsicsPath = "";

		[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
		private static void AutoAttachToMainCamera()
		{
			if (FindObjectOfType<CameraIntrinsicsFromFOV>() != null) return;
			// find main camera
			GameObject mainCameraObj = GameObject.FindGameObjectWithTag("MainCamera");
			if (mainCameraObj == null) { Debug.LogWarning("[CameraIntrinsics] No MainCamera found"); return; }
			var intrinsics = mainCameraObj.AddComponent<CameraIntrinsicsFromFOV>();
			intrinsics.targetCamera = mainCameraObj.GetComponent<Camera>();
			Debug.Log($"[CameraIntrinsics] Auto-attached to MainCamera: {mainCameraObj.name}");
		}

		// Optional: invoke on start if desired
		// void Start() { config = CameraExtractionConfig.Load(); CalculateAndLogIntrinsics(); }

		public void CalculateAndLogIntrinsics()
		{
			if (config == null) config = CameraExtractionConfig.Load();
			var cam = targetCamera != null ? targetCamera : Camera.main; if (cam == null) return;
			// Prefer configured screenshot resolution if provided, to match captures
			w = (config.screenshotWidth > 0) ? config.screenshotWidth : cam.pixelWidth;
			h = (config.screenshotHeight > 0) ? config.screenshotHeight : cam.pixelHeight;
			fovDeg = cam.fieldOfView;
			float fovRad = fovDeg * Mathf.Deg2Rad; fy = (h * 0.5f) / Mathf.Tan(fovRad * 0.5f); float aspect = (float)w / h; fx = fy * aspect; cx = w * 0.5f; cy = h * 0.5f;
			if (cam.usePhysicalProperties && cam.lensShift != Vector2.zero) { cx += cam.lensShift.x * w * 0.5f; cy += cam.lensShift.y * h * 0.5f; }
			string info = $"[CameraIntrinsics] K = [[{fx:F3}, 0, {cx:F3}], [0, {fy:F3}, {cy:F3}], [0, 0, 1]] (w={w}, h={h}, fov={fovDeg:F3}deg, aspect={(float)w/h:F3})";
			Debug.Log(info);
			if (saveToFile) SaveIntrinsicsToFile(info);
		}
		
		/// <summary>
		/// Calculate intrinsics with agent ID and timestamp for filename formatting
		/// </summary>
		public void CalculateAndLogIntrinsicsWithAgentInfo(string agentId, string agentTimestamp)
		{
			if (config == null) config = CameraExtractionConfig.Load();
			var cam = targetCamera != null ? targetCamera : Camera.main; if (cam == null) return;
			// Prefer configured screenshot resolution if provided, to match captures
			w = (config.screenshotWidth > 0) ? config.screenshotWidth : cam.pixelWidth;
			h = (config.screenshotHeight > 0) ? config.screenshotHeight : cam.pixelHeight;
			fovDeg = cam.fieldOfView;
			float fovRad = fovDeg * Mathf.Deg2Rad; fy = (h * 0.5f) / Mathf.Tan(fovRad * 0.5f); float aspect = (float)w / h; fx = fy * aspect; cx = w * 0.5f; cy = h * 0.5f;
			if (cam.usePhysicalProperties && cam.lensShift != Vector2.zero) { cx += cam.lensShift.x * w * 0.5f; cy += cam.lensShift.y * h * 0.5f; }
			string info = $"[CameraIntrinsics] K = [[{fx:F3}, 0, {cx:F3}], [0, {fy:F3}, {cy:F3}], [0, 0, 1]] (w={w}, h={h}, fov={fovDeg:F3}deg, aspect={(float)w/h:F3})";
			Debug.Log(info);
			if (saveToFile) SaveIntrinsicsToFileWithAgentInfo(info, agentId, agentTimestamp);
		}

		public void ExtractIntrinsicsNow()
		{
			if (config == null) config = CameraExtractionConfig.Load();
			CalculateAndLogIntrinsics();
		}
		
		/// <summary>
		/// Extract intrinsics with agent ID and timestamp for filename formatting
		/// </summary>
		public void ExtractIntrinsicsNowWithAgentInfo(string agentId, string agentTimestamp)
		{
			if (config == null) config = CameraExtractionConfig.Load();
			CalculateAndLogIntrinsicsWithAgentInfo(agentId, agentTimestamp);
		}

		public void Configure(Camera cam, string intrinsicsDir)
		{
			targetCamera = cam;
			customIntrinsicsPath = intrinsicsDir;
			if (config == null) config = CameraExtractionConfig.Load();
		}

		void SaveIntrinsicsToFile(string intrinsicsInfo)
		{
			try
			{
				string timestamp = System.DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
                var projectName = CameraExtractionConfig.GetProjectName(); 
				string cameraName = targetCamera != null ? targetCamera.gameObject.name : "Camera";
				string camNameSafe = SanitizeName(cameraName);
				string filename = $"{projectName}_{camNameSafe}_camera_intrinsics_{timestamp}.txt"; 
				string outputDir = string.IsNullOrEmpty(customIntrinsicsPath) ? config.GetIntrinsicsPathForCamera(cameraName) : customIntrinsicsPath;
				Directory.CreateDirectory(outputDir);
				string filePath = Path.Combine(outputDir, filename);
				
				using (var writer = new StreamWriter(filePath))
				{
					writer.WriteLine("# Camera Intrinsics Matrix K");
					writer.WriteLine($"# Generated at: {System.DateTime.UtcNow:o}");
					writer.WriteLine($"# Resolution: {w}x{h}");
					writer.WriteLine($"# FOV: {fovDeg:F3} degrees");
					writer.WriteLine($"# Aspect Ratio: {(float)w/h:F3}");
					writer.WriteLine();
					writer.WriteLine("# 3x3 Intrinsic Matrix K:");
					writer.WriteLine($"# K = [[{fx:F6}, 0, {cx:F6}],");
					writer.WriteLine($"#      [0, {fy:F6}, {cy:F6}],");
					writer.WriteLine("#      [0, 0, 1]]");
					writer.WriteLine();
					writer.WriteLine("# Matrix elements (row-major order):");
					writer.WriteLine($"{fx:F6}, 0, {cx:F6}");
					writer.WriteLine($"0, {fy:F6}, {cy:F6}");
					writer.WriteLine("0, 0, 1");
				}
				Debug.Log($"[CameraIntrinsics] Saved intrinsics to: {filePath}");
			}
			catch (System.Exception e) { Debug.LogError($"[CameraIntrinsics] Failed to save intrinsics: {e}"); }
		}
		
		/// <summary>
		/// Save intrinsics with agent ID and timestamp in filename
		/// </summary>
		void SaveIntrinsicsToFileWithAgentInfo(string intrinsicsInfo, string agentId, string agentTimestamp)
		{
			try
			{
				var projectName = CameraExtractionConfig.GetProjectName(); 
				string cameraName = targetCamera != null ? targetCamera.gameObject.name : "Camera";
				string camNameSafe = SanitizeName(cameraName);
				
				// Build filename with agent ID and timestamp if provided
				string filenamePrefix = "";
				if (!string.IsNullOrEmpty(agentId))
				{
					string safeAgentId = SanitizeName(agentId);
					string timestampPart = !string.IsNullOrEmpty(agentTimestamp) ? agentTimestamp : System.DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
					filenamePrefix = $"{safeAgentId}_{timestampPart}_";
				}
				else
				{
					string timestamp = System.DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
					filenamePrefix = $"{timestamp}_";
				}
				
				string filename = $"{filenamePrefix}{projectName}_{camNameSafe}_camera_intrinsics.txt"; 
				string outputDir = string.IsNullOrEmpty(customIntrinsicsPath) ? config.GetIntrinsicsPathForCamera(cameraName) : customIntrinsicsPath;
				
				Directory.CreateDirectory(outputDir);
				string filePath = Path.Combine(outputDir, filename);
				
				using (var writer = new StreamWriter(filePath))
				{
					writer.WriteLine("# Camera Intrinsics Matrix K");
					writer.WriteLine($"# Generated at: {System.DateTime.UtcNow:o}");
					if (!string.IsNullOrEmpty(agentId))
					{
						writer.WriteLine($"# Agent ID: {agentId}");
						writer.WriteLine($"# Agent Timestamp: {agentTimestamp}");
					}
					writer.WriteLine($"# Resolution: {w}x{h}");
					writer.WriteLine($"# FOV: {fovDeg:F3} degrees");
					writer.WriteLine($"# Aspect Ratio: {(float)w/h:F3}");
					writer.WriteLine();
					writer.WriteLine("# 3x3 Intrinsic Matrix K:");
					writer.WriteLine($"# K = [[{fx:F6}, 0, {cx:F6}],");
					writer.WriteLine($"#      [0, {fy:F6}, {cy:F6}],");
					writer.WriteLine("#      [0, 0, 1]]");
					writer.WriteLine();
					writer.WriteLine("# Matrix elements (row-major order):");
					writer.WriteLine($"{fx:F6}, 0, {cx:F6}");
					writer.WriteLine($"0, {fy:F6}, {cy:F6}");
					writer.WriteLine("0, 0, 1");
				}
				Debug.Log($"[CameraIntrinsics] Saved intrinsics to: {filePath}");
			}
			catch (System.Exception e) { Debug.LogError($"[CameraIntrinsics] Failed to save intrinsics: {e}"); }
		}

		private static string SanitizeName(string name)
		{
			if (string.IsNullOrEmpty(name)) return "Camera";
			foreach (char c in System.IO.Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
			return name;
		}
	}
}