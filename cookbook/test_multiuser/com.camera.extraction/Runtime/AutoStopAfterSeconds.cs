using System.Collections;
using UnityEngine;

namespace CameraExtraction
{
	public class AutoStopAfterSeconds : MonoBehaviour
	{
		public float seconds = 5f;

		void Start()
		{
			StartCoroutine(StopCo());
		}

		IEnumerator StopCo()
		{
			yield return new WaitForSeconds(seconds);
#if UNITY_EDITOR
			UnityEditor.EditorApplication.isPlaying = false;
			UnityEditor.EditorApplication.Exit(0);
#else
			Application.Quit();
#endif
		}
	}
}


