using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace CameraExtraction.Editor
{
	/// <summary>
	/// Minimal manifest editor to add/remove/check this package as a dependency
	/// in a Unity project's Packages/manifest.json. Uses light string manipulation
	/// to avoid external JSON dependencies inside the editor assembly.
	/// </summary>
	public static class ManifestManager
	{
		public const string PackageName = "com.camera.extraction";

		public static bool AddPackageToManifest(string unityProjectPath, string packagePathOrNull)
		{
			try
			{
				string manifestPath = GetManifestPath(unityProjectPath);
				if (!File.Exists(manifestPath))
				{
					Debug.LogError($"[ManifestManager] manifest.json not found: {manifestPath}");
					return false;
				}

				string manifest = File.ReadAllText(manifestPath, Encoding.UTF8);
				string dependencyValue = BuildDependencyValue(unityProjectPath, packagePathOrNull);

				if (IsPackageInManifestContent(manifest))
				{
					// Update existing entry
					string updated = Regex.Replace(
						manifest,
						$"\"{Regex.Escape(PackageName)}\"\\s*:\\s*\"[^\"]*\"",
						$"\"{PackageName}\": \"{dependencyValue}\""
					);
					File.WriteAllText(manifestPath, updated, Encoding.UTF8);
					return true;
				}

				// Insert new entry inside dependencies object
				int depsStart = FindDependenciesStart(manifest);
				if (depsStart < 0)
				{
					Debug.LogError("[ManifestManager] 'dependencies' section not found in manifest.json");
					return false;
				}

				int depsEnd = FindObjectEnd(manifest, depsStart);
				if (depsEnd < 0)
				{
					Debug.LogError("[ManifestManager] Could not parse dependencies object in manifest.json");
					return false;
				}

				// Determine indentation
				string indent = DetectIndentation(manifest, depsStart);
				string newline = DetectNewline(manifest);

				// Check if there are existing entries to decide comma placement
				string depsBody = manifest.Substring(depsStart + 1, depsEnd - depsStart - 1);
				bool hasAnyEntry = Regex.IsMatch(depsBody, @"""[^""]+""\s*:\s*""[^""]*""");

				string insertion = (hasAnyEntry ? "," : string.Empty) + newline + indent + $"\"{PackageName}\": \"{dependencyValue}\"" + newline;

				var sb = new StringBuilder();
				sb.Append(manifest.Substring(0, depsEnd));
				sb.Append(insertion);
				sb.Append(manifest.Substring(depsEnd));

				File.WriteAllText(manifestPath, sb.ToString(), Encoding.UTF8);
				return true;
			}
			catch (Exception ex)
			{
				Debug.LogError($"[ManifestManager] Add failed: {ex}");
				return false;
			}
		}

		public static bool RemovePackageFromManifest(string unityProjectPath)
		{
			try
			{
				string manifestPath = GetManifestPath(unityProjectPath);
				if (!File.Exists(manifestPath))
				{
					Debug.LogError($"[ManifestManager] manifest.json not found: {manifestPath}");
					return false;
				}

				string manifest = File.ReadAllText(manifestPath, Encoding.UTF8);
				if (!IsPackageInManifestContent(manifest)) return true; // nothing to do

				// Remove the property and handle trailing/leading commas
				string pattern = $"(^|\n|\r\n)\\s*\"{Regex.Escape(PackageName)}\"\\s*:\\s*\"[^\\\"]*\"\\s*(,)?";
				string updated = Regex.Replace(manifest, pattern, m =>
				{
					bool hadComma = m.Groups.Count >= 3 && m.Groups[2].Success;
					string prefix = m.Groups[1].Value; // newline or start
					return hadComma ? prefix : prefix; // entry removed; surrounding commas managed by subsequent replace
				}, RegexOptions.Multiline);

				// Fix any trailing commas before closing brace of dependencies
				updated = Regex.Replace(updated, @"(\n|\r\n)(\s*),\s*(\n|\r\n)(\s*})", "$1$4");

				File.WriteAllText(manifestPath, updated, Encoding.UTF8);
				return true;
			}
			catch (Exception ex)
			{
				Debug.LogError($"[ManifestManager] Remove failed: {ex}");
				return false;
			}
		}

		public static bool IsPackageInManifest(string unityProjectPath)
		{
			try
			{
				string manifestPath = GetManifestPath(unityProjectPath);
				if (!File.Exists(manifestPath)) return false;
				string manifest = File.ReadAllText(manifestPath, Encoding.UTF8);
				return IsPackageInManifestContent(manifest);
			}
			catch
			{
				return false;
			}
		}

		private static string GetManifestPath(string unityProjectPath)
		{
			return Path.Combine(unityProjectPath, "Packages", "manifest.json");
		}

		private static bool IsPackageInManifestContent(string manifestJson)
		{
			return Regex.IsMatch(manifestJson, $"\"{Regex.Escape(PackageName)}\"\\s*:\\s*\"[^\"]*\"");
		}

		private static string BuildDependencyValue(string unityProjectPath, string packagePathOrNull)
		{
			// If a path is given, prefer absolute path. Unity supports file: with absolute or relative.
			if (!string.IsNullOrEmpty(packagePathOrNull))
			{
				string path = packagePathOrNull;
				if (!Path.IsPathRooted(path))
				{
					// make relative to project root if relative was provided
					path = Path.GetFullPath(Path.Combine(unityProjectPath, path));
				}
				return $"file:{path.Replace("\\", "/")}";
			}

			// Fallback: assume the package folder sits beside the Unity project and use a relative path
			// This is a heuristic; callers should pass --package-path for reliability.
			string relativeGuess = "../unity_package/com.camera.extraction";
			return $"file:{relativeGuess}";
		}

		private static int FindDependenciesStart(string json)
		{
			int keyIndex = Regex.Match(json, @"""dependencies""\s*:\s*\{").Index;
			if (keyIndex < 0) return -1;
			return json.IndexOf('{', keyIndex);
		}

		private static int FindObjectEnd(string json, int openBraceIndex)
		{
			int depth = 0;
			for (int i = openBraceIndex; i < json.Length; i++)
			{
				char c = json[i];
				if (c == '{') depth++;
				else if (c == '}')
				{
					depth--;
					if (depth == 0) return i;
				}
			}
			return -1;
		}

		private static string DetectIndentation(string json, int depsStart)
		{
			int lineStart = json.LastIndexOf('\n', depsStart);
			if (lineStart < 0) lineStart = 0;
			int i = lineStart + 1;
			while (i < json.Length && (json[i] == ' ' || json[i] == '\t')) i++;
			// Add an extra level of indentation compared to the line containing '{'
			string baseIndent = json.Substring(lineStart + 1, i - (lineStart + 1));
			return baseIndent + (baseIndent.Contains("\t") ? "\t" : "\t");
		}

		private static string DetectNewline(string json)
		{
			return json.Contains("\r\n") ? "\r\n" : "\n";
		}
	}
}



