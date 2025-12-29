# com.camera.extraction

Extract per-camera intrinsics, poses, and screenshots from a Unity scene. Supports the Main Camera and up to N additional scene objects discovered at runtime. Outputs are organized per camera to avoid mixing data.

## Features
- Automatically attaches to Main Camera
- Dynamically finds additional scene objects and ensures (add camera component) they have `Camera` components
- Per-camera outputs for:
  - Intrinsics (3x3 K matrix)
  - Poses (position + quaternion) over time
  - Screenshots (offscreen for non-main cameras)
- Filenames including project and camera names

## Installation
- first create a `unity_Projects_list.txt` and list the path to all your unity projects.
- run `add_camera_extraction.py` to put the package into projects dependencies.

## Configuration (camera_extraction_config.json)
Key fields:
- `outputBasePath`: Root for outputs (e.g. `E:\CS_FYP\camera_extraction\outputs`)
- `useProjectSubfolder`: When true, outputs under `{outputBasePath}/{ProjectName}`
- `frameInterval`: Legacy frame interval (kept for compatibility)
- `screenshotIntervalSeconds`: Screenshot capture interval in seconds (default: 1.0)
- `captureScreenshot`: Toggle screenshot capture
- `durationSeconds`: Auto-stop play duration (used by editor automation)
- `maxTrackedObjects`: Number of non-main scene objects to track, NOT including main camera.
- `screenshotSubfolder`, `posesSubfolder`, `intrinsicsSubfolder`: Subfolder names (will be prefixed by project name automatically)

## Output Structure
Root (if `useProjectSubfolder=true`): `{outputBasePath}/{ProjectName}`
- `{ProjectName}_intrinsics/{CameraName}/{ProjectName}_{CameraName}_camera_intrinsics_{timestamp}.txt`
- `{ProjectName}_poses/{CameraName}/{ProjectName}_{CameraName}_hmd_pose_{timestamp}.csv`
- `{ProjectName}_screenshots/{CameraName}/{ProjectName}_{CameraName}_screenshot_frame_000040.png`

`{CameraName}` is sanitized for filesystem safety.

## Runtime Components

### `Runtime/CameraExtractionConfig.cs`
Central configuration + path helpers.
- `Load()`, `Save()`
- `GetOutputDirectory()`
- `GetScreenshotsPath[ForCamera](name)` / `GetPosesPath[ForCamera](name)` / `GetIntrinsicsPath[ForCamera](name)`
- `GetProjectName()`

### `Runtime/MultiCameraExtractor.cs`
Orchestrator that discovers/maintains camera hosts.
- Auto-attaches on load via `RuntimeInitializeOnLoadMethod(AfterSceneLoad)`
- `InitialSetup()` sets up Main Camera (tag `MainCamera`) and triggers maintenance
- `MaintainTrackedHosts()` rescans every `rescanIntervalSeconds`:
  - Removes destroyed/disabled hosts
  - Keeps Main Camera separate from `maxTrackedObjects`
  - Fills up to `maxTrackedObjects` with best candidates (prefers objects that already have a `Camera`)
- `SetupHost(GameObject)`:
  - Ensures a `Camera` component; disables rendering for non-main cameras so Game view is unaffected
  - Creates per-camera directories
  - Attaches and configures:
    - `CameraIntrinsicsFromFOV.Configure(cam, intrinsicsDir)` then `ExtractIntrinsicsNow()`
    - `CenterEyePoseLogger.Configure(cam, posesDir, screenshotsDir, frameInterval, screenshotIntervalSeconds, captureScreenshot)`

### `Runtime/CenterEyePoseLogger.cs`
Pose logging + optional offscreen screenshots for a specific camera.
- Auto-attach to Main Camera on load (if none exists)
- `Configure(cam, posesDir, screenshotsDir, frameInterval, screenshotInterval, capture)` sets target and initializes output
- `Update()` captures screenshots every `screenshotIntervalSeconds` seconds (pose logging is synchronized with screenshots)
- Filenames include `{ProjectName}` and `{CameraName}`

### `Runtime/CameraIntrinsicsFromFOV.cs`
Computes intrinsics matrix from FOV and resolution; supports lens shift.
- `Configure(cam, intrinsicsDir)`, `ExtractIntrinsicsNow()`
- Writes detailed K matrix and metadata to a per-camera file

### `Runtime/AutoStopAfterSeconds.cs`
Utility to stop play mode/quit after a duration (used by editor automation).

## Command Line Arguments
The following CLI arguments can override configuration settings:
- `--frameInterval=N`: Override legacy frame interval (kept for compatibility)
- `--screenshotInterval=N`: Override screenshot interval in seconds
- `--captureScreenshot=true/false`: Override screenshot capture setting
- `--screenshotDir="path"`: Override screenshot output directory
- `--duration=N`: Override auto-stop duration in seconds

## Outputs
### 1. Camera Intrinsics
(1) Field of View (FOV):  angular extent of the observable scene visible through a camera, i.e. how wide the view is.
(2) Intrinsic Matrix K: 
\[
K=\begin{bmatrix}
f_x & s & c_x \\
0 & f_y & c_y \\
0 & 0 & 1
\end{bmatrix}
\]















