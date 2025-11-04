using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using CameraExtraction; // access runtime types

namespace CameraExtraction.Editor
{
	public static class AttachAndRun
	{
		// Entry: called via -executeMethod CameraExtraction.Editor.AttachAndRun.ProcessProject
		public static void ProcessProject()
		{
			
			string manifestCommand = GetStringArg("--manifest", "");
			if (!string.IsNullOrEmpty(manifestCommand))
			{
				ProcessManifestCommand(manifestCommand);
				return;
			}


			var config = CameraExtractionConfig.Load();
			
			string scene = GetStringArg("--scene", FindFirstScene());
			int playSeconds = GetIntArg("--duration", config.durationSeconds);
			
			if (string.IsNullOrEmpty(scene))
			{
				Debug.LogError("[AttachAndRun] No scene found. Use --scene=Assets/.. or keep at least one scene.");
				EditorApplication.Exit(1);
				return;
			}

			if (!EditorSceneManager.OpenScene(scene).IsValid())
			{
				Debug.LogError($"[AttachAndRun] Failed to open scene: {scene}");
				EditorApplication.Exit(2);
				return;
			}

			// Ensure a MainCamera exists
			var main = GameObject.FindGameObjectWithTag("MainCamera");
			if (main == null)
			{
				var camGo = new GameObject("Main Camera");
				camGo.tag = "MainCamera";
				camGo.AddComponent<Camera>();
				main = camGo;
				Debug.Log("[AttachAndRun] Created Main Camera");
			}

			// Add components if missing (main camera baseline)
			if (main.GetComponent<CenterEyePoseLogger>() == null) main.AddComponent<CenterEyePoseLogger>();
			if (main.GetComponent<CameraIntrinsicsFromFOV>() == null) main.AddComponent<CameraIntrinsicsFromFOV>();

			// Ensure multi-camera orchestrator exists to set up extra hosts
			if (Object.FindObjectOfType<MultiCameraExtractor>() == null)
			{
				new GameObject("__MultiCameraExtractor").AddComponent<MultiCameraExtractor>();
			}

			// Save scene and project to persist attachment
			EditorSceneManager.MarkSceneDirty(main.scene);
			EditorSceneManager.SaveScene(main.scene);
			AssetDatabase.SaveAssets();

			// Attach a runtime stopper to ensure stopping even after domain reload
			var stopperGo = new GameObject("__AutoStopAfterSeconds");
			var stopper = stopperGo.AddComponent<AutoStopAfterSeconds>();
			stopper.seconds = Mathf.Max(0.1f, playSeconds);

			// Start play mode
			EditorApplication.isPlaying = true;
			
			Debug.Log($"[AttachAndRun] Started with duration: {playSeconds}s, output: {config.GetOutputDirectory()}");
		}

		private static string FindFirstScene()
		{
			foreach (var guid in AssetDatabase.FindAssets("t:Scene"))
			{
				var path = AssetDatabase.GUIDToAssetPath(guid);
				if (path.EndsWith(".unity")) return path;
			}
			return string.Empty;
		}

		private static int GetIntArg(string key, int fallback)
		{
			foreach (var arg in System.Environment.GetCommandLineArgs())
				if (arg.StartsWith(key+"=")) { if (int.TryParse(arg.Substring(key.Length+1), out int v)) return v; }
			return fallback;
		}

		private static string GetStringArg(string key, string fallback)
		{
			foreach (var arg in System.Environment.GetCommandLineArgs())
				if (arg.StartsWith(key+"=")) return arg.Substring(key.Length+1).Trim('"');
			return fallback;
		}

		/// <summary>
		/// </summary>
		/// <param name="command"> cmd type:add, remove, check</param>
		private static void ProcessManifestCommand(string command)
		{
			string projectPath = GetStringArg("--project", "");
			string packagePath = GetStringArg("--package-path", "");

			if (string.IsNullOrEmpty(projectPath))
			{
				Debug.LogError("[AttachAndRun] --project parameter is required for manifest commands");
				EditorApplication.Exit(1);
				return;
			}

			bool success = false;
			string finalPackagePath = string.IsNullOrEmpty(packagePath) ? null : packagePath;

			switch (command.ToLower())
			{
				case "add":
					success = ManifestManager.AddPackageToManifest(projectPath, finalPackagePath);
					Debug.Log(success ? "[AttachAndRun] Successfully added package to manifest" : "[AttachAndRun] Failed to add package to manifest");
					break;

				case "remove":
					success = ManifestManager.RemovePackageFromManifest(projectPath);
					Debug.Log(success ? "[AttachAndRun] Successfully removed package from manifest" : "[AttachAndRun] Failed to remove package from manifest");
					break;

				case "check":
					bool isInManifest = ManifestManager.IsPackageInManifest(projectPath);
					Debug.Log($"[AttachAndRun] Package in manifest: {isInManifest}");
					success = true; // Check operation always succeeds
					break;

				default:
					Debug.LogError($"[AttachAndRun] Unknown manifest command: {command}. Use: add, remove, or check");
					EditorApplication.Exit(1);
					return;
			}

			EditorApplication.Exit(success ? 0 : 1);
		}
	}
}