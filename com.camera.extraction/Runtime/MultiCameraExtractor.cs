using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CameraExtraction
{
	// Simple JSON structure for Agent screenshot requests
	[Serializable]
	public class AgentScreenshotRequest
	{
		public string agent_id;
		public string timestamp;
	}

	public class MultiCameraExtractor : MonoBehaviour
	{
		public bool includeMainCamera = true;
		public float rescanIntervalSeconds = 1.0f;
		private float rescanTimer;
		private float globalScreenshotTimer;  // Global timer for synchronized screenshots
		private bool isCapturing; // prevent maintenance during capture
		private CameraExtractionConfig config;
		private readonly List<GameObject> trackedHosts = new List<GameObject>();
		private string trackedHostsLogPath;
		private string agentRequestDir;
		private float agentRequestCheckTimer = 0f;
		private const float agentRequestCheckInterval = 0.1f;  // Check every 100ms
		private string currentAgentId = "";  // Current agent ID for screenshot naming
		private string currentAgentTimestamp = "";  // Current agent timestamp for screenshot naming

		[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
		private static void AutoAttach()
		{
			if (FindObjectOfType<MultiCameraExtractor>() != null) return;
			var go = new GameObject("__MultiCameraExtractor");
			go.AddComponent<MultiCameraExtractor>();
		}

	void Awake()
	{
		config = CameraExtractionConfig.Load();
		rescanTimer = 0f;
		globalScreenshotTimer = 0f;  // Initialize global screenshot timer
		agentRequestCheckTimer = 0f;
		
		// Setup Agent control directory (use config value, or default to outputBasePath/agent_requests)
		if (string.IsNullOrEmpty(config.agentControlRequestDir))
		{
			// Default to outputBasePath/agent_requests (not project subfolder)
			string basePath = string.IsNullOrEmpty(config.outputBasePath) ? 
				Application.persistentDataPath : config.outputBasePath;
			agentRequestDir = Path.Combine(basePath, "agent_requests");
		}
		else
		{
			agentRequestDir = config.agentControlRequestDir;
		}
		Directory.CreateDirectory(agentRequestDir);
		Debug.Log($"[MultiCameraExtractor] Agent request directory: {agentRequestDir}");
		
		InitializeTrackedHostsLogger();
		InitialSetup();
	}

	void Update()
	{
		// 1) Check for Agent screenshot requests (if auto screenshot is disabled)
		if (!config.autoScreenshotEnabled)
		{
			agentRequestCheckTimer += Time.deltaTime;
			if (agentRequestCheckTimer >= agentRequestCheckInterval)
			{
				agentRequestCheckTimer = 0f;
				CheckAndProcessAgentRequests();
			}
		}
		else
		{
			// 2) Auto screenshot mode: Decide capture first (so maintenance won't collide within this frame)
			globalScreenshotTimer += Time.deltaTime;
			bool shouldCapture = globalScreenshotTimer >= config.screenshotIntervalSeconds;
			if (shouldCapture)
			{
				globalScreenshotTimer = 0f;
				isCapturing = true;
				
				// CRITICAL: Filter out wall-occluded hosts immediately before capturing
				if (config.filterByWallOcclusion)
				{
					FilterOccludedHosts();
				}
				
				// Shared timestamp (only used by timestamp organization mode)
				string sharedTimestamp = System.DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
				currentAgentId = "";  // No agent ID in auto mode
				currentAgentTimestamp = sharedTimestamp;
				TriggerAllScreenshots(sharedTimestamp);
				isCapturing = false;
			}
		}

		// 3) Only maintain when not capturing in this frame
		rescanTimer += Time.deltaTime;
		if (!isCapturing && rescanTimer >= rescanIntervalSeconds)
		{
			rescanTimer = 0f;
			MaintainTrackedHosts();
		}

		AppendTrackedHostsLog();
	}

	private void CheckAndProcessAgentRequests()
	{
		if (isCapturing) return;  // Don't process new requests while capturing
		
		try
		{
			// Look for request files in the agent request directory
			var requestFiles = Directory.GetFiles(agentRequestDir, "*.request");
			foreach (var requestFile in requestFiles)
			{
				try
				{
					string jsonContent = File.ReadAllText(requestFile);
					var request = JsonUtility.FromJson<AgentScreenshotRequest>(jsonContent);
					
					if (request != null && !string.IsNullOrEmpty(request.agent_id))
					{
						// Process the request
						isCapturing = true;
						currentAgentId = request.agent_id;
						currentAgentTimestamp = !string.IsNullOrEmpty(request.timestamp) 
							? request.timestamp 
							: System.DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
						
						// Filter out wall-occluded hosts immediately before capturing
						if (config.filterByWallOcclusion)
						{
							FilterOccludedHosts();
						}
						
						// Trigger screenshots with agent ID and timestamp
						TriggerAllScreenshots(currentAgentTimestamp);
						isCapturing = false;
						
						// Delete the request file after processing
						try
						{
							File.Delete(requestFile);
						}
						catch (Exception e)
						{
							Debug.LogWarning($"[MultiCameraExtractor] Failed to delete request file {requestFile}: {e.Message}");
						}
						
						Debug.Log($"[MultiCameraExtractor] ✅ Processed Agent screenshot request: agent_id={request.agent_id}, timestamp={currentAgentTimestamp}");
						break;  // Process one request per frame
					}
				}
				catch (Exception e)
				{
					Debug.LogWarning($"[MultiCameraExtractor] Failed to process request file {requestFile}: {e.Message}");
					// Try to delete malformed request file
					try { File.Delete(requestFile); } catch { }
				}
			}
		}
		catch (Exception e)
		{
			Debug.LogWarning($"[MultiCameraExtractor] Error checking agent requests: {e.Message}");
		}
	}

		private void InitialSetup()
		{
			// Ensure main camera baseline is configured, if requested
			if (includeMainCamera)
			{
				var mainObj = GameObject.FindGameObjectWithTag("MainCamera");
				if (mainObj != null) SetupHost(mainObj);
			}
			MaintainTrackedHosts();
		}

		private void FilterOccludedHosts()
		{
			// Filter out hosts that are currently occluded by walls from Main Camera
			// This is called immediately before each screenshot to ensure accuracy
			var mainObj = includeMainCamera ? GameObject.FindGameObjectWithTag("MainCamera") : null;
			if (mainObj == null) return;

			var keywords = ParseWallKeywords(config.wallNameKeywords);
			int removedCount = 0;
			
			for (int i = trackedHosts.Count - 1; i >= 0; i--)
			{
				var h = trackedHosts[i];
				if (h == null || (includeMainCamera && h.CompareTag("MainCamera"))) continue;
				
				if (HasWallBetweenByName(mainObj.transform, h.transform, keywords, config.visibilitySampleVerticalOffset))
				{
					Debug.LogWarning($"[MultiCameraExtractor] 🚫 PRE-CAPTURE FILTER: Removing '{h.name}' (id={h.GetInstanceID()}) - blocked by wall/boundary from MainCamera. This screenshot will be skipped.");
					trackedHosts.RemoveAt(i);
					removedCount++;
				}
			}
			
			if (removedCount > 0)
			{
				Debug.LogWarning($"[MultiCameraExtractor] ⚠️ Pre-capture filtering removed {removedCount} wall-occluded host(s) before screenshot.");
			}
		}

	private void MaintainTrackedHosts()
		{
		if (isCapturing) return; // do not modify list during a capture pass
			// Clean up destroyed/disabled (preserve MainCamera even if inactive)
			trackedHosts.RemoveAll(h => h == null || (!h.CompareTag("MainCamera") && !h.activeInHierarchy));
			// Clean up XR Interaction objects (preserve MainCamera regardless of XR checks)
	    	trackedHosts.RemoveAll(h => h != null && !h.CompareTag("MainCamera") && IsXRInteractionObject(h));

			// Optional: prune hosts that are occluded by walls/boundaries from the Main Camera
			if (config.filterByWallOcclusion)
			{
				var mainObj = includeMainCamera ? GameObject.FindGameObjectWithTag("MainCamera") : null;
				if (mainObj != null)
				{
					var keywords = ParseWallKeywords(config.wallNameKeywords);
					for (int i = trackedHosts.Count - 1; i >= 0; i--)
					{
						var h = trackedHosts[i];
						if (h == null || (includeMainCamera && h.CompareTag("MainCamera"))) continue;
						if (HasWallBetweenByName(mainObj.transform, h.transform, keywords, config.visibilitySampleVerticalOffset))
						{
							Debug.Log($"[MultiCameraExtractor] ✂️ Pruned tracked host '{h.name}' (id={h.GetInstanceID()}) - blocked by wall/boundary from MainCamera.");
							trackedHosts.RemoveAt(i);
						}
					}
				}
			}

			int targetCount = Mathf.Max(0, config.maxTrackedObjects);
			// Exclude main camera from the quota (it's handled separately)
			if (includeMainCamera)
			{
				var mainObj = GameObject.FindGameObjectWithTag("MainCamera");
				// if main camera is not in tracked hosts, add it
				if (mainObj != null && !trackedHosts.Contains(mainObj)) SetupHost(mainObj);
				// remove duplicate main camera
				trackedHosts.RemoveAll(h => h != null && h.CompareTag("MainCamera") && h != mainObj);
			}

			// Fill up to targetCount with best available scene objects
			if (CountNonMain(trackedHosts) < targetCount)
			{
				var mainObj = includeMainCamera ? GameObject.FindGameObjectWithTag("MainCamera") : null;
				var keywords = config.filterByWallOcclusion ? ParseWallKeywords(config.wallNameKeywords) : null;
				
				foreach (var candidate in EnumerateSceneCandidates())
				{
					if (includeMainCamera && candidate.CompareTag("MainCamera")) continue;
					if (trackedHosts.Contains(candidate)) continue;
					
					// If enabled, skip candidates occluded from Main Camera by walls/boundaries
					if (config.filterByWallOcclusion && mainObj != null && keywords != null)
					{
						if (HasWallBetweenByName(mainObj.transform, candidate.transform, keywords, config.visibilitySampleVerticalOffset))
						{
							Debug.Log($"[MultiCameraExtractor] ❌ Filtered out candidate '{candidate.name}' (id={candidate.GetInstanceID()}) - blocked by wall/boundary from MainCamera.");
							continue;
						}
					}
					
					SetupHost(candidate);
					if (CountNonMain(trackedHosts) >= targetCount) break;
				}
			}
			else
			{
				// Too many: drop extras that are not main
				int excess = CountNonMain(trackedHosts) - targetCount;
				for (int i = trackedHosts.Count - 1; i >= 0 && excess > 0; i--)
				{
					var h = trackedHosts[i];
					if (h != null && (!includeMainCamera || !h.CompareTag("MainCamera")))
					{
						trackedHosts.RemoveAt(i);
						excess--;
					}
				}
			}

			
		}

		private int CountNonMain(List<GameObject> list)
		{
			if (!includeMainCamera) return list.Count;
			int c = 0;
			for (int i = 0; i < list.Count; i++) if (list[i] != null && !list[i].CompareTag("MainCamera")) c++;
			return c;
		}

	private IEnumerable<GameObject> EnumerateSceneCandidates()
	{
		// All active objects in the active scene(s)
		var all = Resources.FindObjectsOfTypeAll<GameObject>()
			.Where(go => go.scene.IsValid() && go.activeInHierarchy && (go.hideFlags & HideFlags.HideInHierarchy) == 0)
			.Where(go => go != this.gameObject)
			.Where(go => IsTransformValid(go.transform))
			.Where(go => !IsXRInteractionObject(go));
		// Prefer objects that already have a Camera, then others; stable order by name then instance id
		var withCam = all.Where(go => go.GetComponent<Camera>() != null)
			.OrderBy(go => go.name, StringComparer.Ordinal)
			.ThenBy(go => go.GetInstanceID());
		var withoutCam = all.Where(go => go.GetComponent<Camera>() == null)
			.OrderBy(go => go.name, StringComparer.Ordinal)
			.ThenBy(go => go.GetInstanceID());
		foreach (var go in withCam) yield return go;
		foreach (var go in withoutCam) yield return go;
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
		// Reject extremely far objects (>|1e6| units from origin)
		if (p.sqrMagnitude > 1e12f) return false;
		// Reject zero or extreme scales
		if (s.x == 0f || s.y == 0f || s.z == 0f) return false;
		if (Mathf.Abs(s.x) > 1e6f || Mathf.Abs(s.y) > 1e6f || Mathf.Abs(s.z) > 1e6f) return false;
		return true;
	}

	private static bool IsXRInteractionObject(GameObject go)
	{
		// Skip XR interaction system objects by name
		string name = go.name.ToLowerInvariant();
		if (name.Contains("interactor") || name.Contains("xr origin") || name.Contains("xr rig") ||
		    (name.Contains("hand") && (name.Contains("left") || name.Contains("right"))) ||
		    name.Contains("controller") || name.Contains("teleport") ||
		    name.Contains("linevisual") || name.Contains("line visual") || 
		    name.Contains("reticle") || name.Contains("visual"))
			return true;
		
		// Check if any parent is an XR Interaction object
		Transform parent = go.transform.parent;
		while (parent != null)
		{
			string parentName = parent.name.ToLowerInvariant();
			if (parentName.Contains("interactor") || parentName.Contains("xr origin") || parentName.Contains("xr rig") ||
		    (parentName.Contains("hand") && (parentName.Contains("left") || parentName.Contains("right"))) ||
		    parentName.Contains("controller") || parentName.Contains("teleport") ||
		    parentName.Contains("linevisual") || parentName.Contains("line visual") || 
		    parentName.Contains("reticle") || parentName.Contains("visual"))
				return true;
			parent = parent.parent;
		}
		
		// Skip if has XR Interaction Toolkit components
		var components = go.GetComponents<Component>();
		foreach (var c in components)
		{
			if (c == null) continue;
			string typeName = c.GetType().FullName;
			if (typeName.Contains("XR.Interaction") || typeName.Contains("Interactor") || 
			    typeName.Contains("XRController") || typeName.Contains("TrackedPose"))
				return true;
		}
		return false;
	}

	private void SetupHost(GameObject host)
	{
            // add camera component if not present
		if (host == null) return;
		if (!IsTransformValid(host.transform)) return;
		var cam = host.GetComponent<Camera>();
			if (cam == null) cam = host.AddComponent<Camera>();
			
			// Apply uniform FOV if enabled
			if (config.useUniformFOV)
			{
				cam.fieldOfView = config.uniformFOV;
				Debug.Log($"[MultiCameraExtractor] Set uniform FOV={config.uniformFOV}° for camera '{host.name}'");
			}
			
			bool isMain = includeMainCamera && host.CompareTag("MainCamera");
			if (!isMain)
			{
				// Prevent non-main cameras from affecting on-screen rendering
				cam.enabled = false;
				cam.clearFlags = CameraClearFlags.Depth;
				cam.depth = -100f;
			}

			if (!trackedHosts.Contains(host)) trackedHosts.Add(host);

			string cameraName = host.name;
			string uniqueCameraId = cameraName + "__" + host.GetInstanceID();
			// Ensure per-camera directories
			string intrinsicsDir = config.GetIntrinsicsPathForCamera(uniqueCameraId);
			string posesDir = config.GetPosesPathForCamera(uniqueCameraId);
			string screenshotsDir = config.GetScreenshotsPathForCamera(uniqueCameraId);
			Directory.CreateDirectory(intrinsicsDir);
			Directory.CreateDirectory(posesDir);
			Directory.CreateDirectory(screenshotsDir);

			// Intrinsics extractor
			var intrinsics = host.GetComponent<CameraIntrinsicsFromFOV>();
			if (intrinsics == null) intrinsics = host.AddComponent<CameraIntrinsicsFromFOV>();
			intrinsics.Configure(cam, intrinsicsDir);
			intrinsics.saveToFile = true;
			intrinsics.ExtractIntrinsicsNow();

			// Pose logger
			var poseLogger = host.GetComponent<CenterEyePoseLogger>();
			if (poseLogger == null) poseLogger = host.AddComponent<CenterEyePoseLogger>();
			poseLogger.Configure(cam, posesDir, screenshotsDir, Mathf.Max(1, config.frameInterval), config.poseIntervalSeconds, config.screenshotIntervalSeconds, config.captureScreenshot);

		Debug.Log($"[MultiCameraExtractor] Setup for '{cameraName}' (id={host.GetInstanceID()}). Output: intrinsics={intrinsicsDir}, poses={posesDir}, screenshots={screenshotsDir}");
	}

	private void TriggerAllScreenshots(string sharedTimestamp)
	{
		// Trigger synchronized screenshot and pose logging for a stable snapshot
		int successCount = 0;
		int failCount = 0;
		// Stable snapshot to avoid concurrent modification
		List<GameObject> snapshot = trackedHosts.Where(h => h != null).ToList();
		foreach (var host in snapshot)
		{
			if (host == null) continue;
			var poseLogger = host.GetComponent<CenterEyePoseLogger>();
			if (poseLogger == null) continue;
			// Pass agent ID and timestamp for custom filename formatting
			bool success = poseLogger.TriggerScreenshotAndPose(sharedTimestamp, currentAgentId, currentAgentTimestamp);
			if (success) successCount++; else failCount++;
		}
		Debug.Log($"[MultiCameraExtractor] Global screenshot trigger: {successCount} succeeded, {failCount} failed (Total tracked snapshot: {snapshot.Count})");
	}

	private void InitializeTrackedHostsLogger()
		{
			try
			{
				string outputDir = config.GetOutputDirectory();
				Directory.CreateDirectory(outputDir);
				trackedHostsLogPath = Path.Combine(outputDir, "tracked_hosts.txt");
				if (!File.Exists(trackedHostsLogPath))
				{
					File.AppendAllText(trackedHostsLogPath, $"# Tracked hosts log started {DateTime.Now:O}{Environment.NewLine}");
				}
			}
			catch (Exception e)
			{
				Debug.LogWarning($"[MultiCameraExtractor] Failed to initialize tracked hosts logger: {e.Message}");
			}
		}

		private void AppendTrackedHostsLog()
		{
			try
			{
				if (string.IsNullOrEmpty(trackedHostsLogPath)) return;
				var valid = trackedHosts.Where(h => h != null).ToList();
				int count = valid.Count;
				string names = string.Join(", ", valid.Select(h => $"{h.name}_{h.GetInstanceID()}"));
				string line = $"{DateTime.Now:O}\tcount={count}\t[{names}]" + Environment.NewLine;
				File.AppendAllText(trackedHostsLogPath, line);
			}
			catch (Exception e)
			{
				Debug.LogWarning($"[MultiCameraExtractor] Failed to append tracked hosts log: {e.Message}");
			}
		}

		// Wall occlusion detection utilities
		private static string[] ParseWallKeywords(string keywordString)
		{
			if (string.IsNullOrEmpty(keywordString)) return new string[] { "boundary", "wall" };
			return keywordString.Split(new char[] { ',', ';', '|' }, StringSplitOptions.RemoveEmptyEntries)
				.Select(k => k.Trim().ToLowerInvariant())
				.Where(k => !string.IsNullOrEmpty(k))
				.ToArray();
		}

		private static Vector3 GetVisualPoint(GameObject go)
		{
			if (go != null && go.TryGetComponent<Renderer>(out var r)) return r.bounds.center;
			return go != null ? go.transform.position : Vector3.zero;
		}

	private static bool HasWallBetweenByName(Transform fromTrans, Transform toTrans, string[] keywords, float verticalOffset = 0.2f)
	{
		if (fromTrans == null || toTrans == null || keywords == null || keywords.Length == 0) return false;

		Vector3 baseFrom = GetVisualPoint(fromTrans.gameObject);
		Vector3 baseTo = GetVisualPoint(toTrans.gameObject);
		float directDist = Vector3.Distance(baseFrom, baseTo);
		
		Debug.Log($"[MultiCameraExtractor] 🔍 Checking wall occlusion between '{fromTrans.name}' and '{toTrans.name}' (distance={directDist:F2}m, keywords={string.Join(",", keywords)})");

		// Multi-sample for robustness (center + up/down offsets)
		Vector3[] samplesFrom = new Vector3[] { baseFrom, baseFrom + Vector3.up * verticalOffset, baseFrom - Vector3.up * verticalOffset };
		Vector3[] samplesTo = new Vector3[] { baseTo, baseTo + Vector3.up * verticalOffset, baseTo - Vector3.up * verticalOffset };

		int totalChecks = 0;
		int blockedChecks = 0;

			foreach (var from in samplesFrom)
			{
				foreach (var to in samplesTo)
				{
					totalChecks++;
					Vector3 dir = to - from;
					float dist = dir.magnitude;
					if (dist < 0.001f) continue;

				// Cast all hits along the ray - IMPORTANT: Include triggers (boundaries are often triggers)
				RaycastHit[] hits = Physics.RaycastAll(from, dir.normalized, dist, Physics.AllLayers, QueryTriggerInteraction.Collide);
				foreach (var hit in hits)
				{
					if (hit.collider == null) continue;
					// Skip self and target
					if (hit.transform == fromTrans || hit.transform == toTrans) continue;

					// Check name hierarchy for wall keywords
					if (IsWallByName(hit.transform, keywords))
					{
						blockedChecks++;
						Debug.Log($"[MultiCameraExtractor] 🚧 Wall/boundary detected: '{hit.transform.name}' " +
							$"blocks path between '{fromTrans.name}' and '{toTrans.name}' " +
							$"(distance={hit.distance:F2}m, layer={hit.collider.gameObject.layer}, isTrigger={hit.collider.isTrigger})");
						// Any single blocked path means occlusion - immediately return
						Debug.Log($"[MultiCameraExtractor] 🔴 Occlusion confirmed: ANY path blocked ({blockedChecks}/{totalChecks} so far) between '{fromTrans.name}' and '{toTrans.name}'");
						return true;
					}
				}
		}
	}

	// No walls detected on any path
	Debug.Log($"[MultiCameraExtractor] ✅ No wall occlusion detected between '{fromTrans.name}' and '{toTrans.name}' (checked {totalChecks} ray paths, 0 blocked)");
	return false;
}

		private static bool IsWallByName(Transform t, string[] keywords)
		{
			// Check the transform and all parents up the hierarchy
			while (t != null)
			{
				string name = t.name.ToLowerInvariant();
				foreach (var keyword in keywords)
				{
					if (name.Contains(keyword))
					{
						return true;
					}
				}
				t = t.parent;
			}
			return false;
		}
	}
}

