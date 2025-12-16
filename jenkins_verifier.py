import jenkins
import time
import argparse
import sys

TEST_CONFIG = {
    "ARTIFACT_NAME": "output.txt",
    "EXPECTED_CONTENT": "Build Verified",
    "MATLAB_ROOT_LINUX": "/home/adutt/MATLAB/R2025a/bin"
}


def trigger_build(server, job_name):
    print(f"1. [ACTION] Triggering build for job: {job_name}")
    queue_id = server.build_job(job_name)
    print(f"   -> Job queued. Queue ID: {queue_id}")
    return queue_id

def get_build_number(server, queue_id):
    print("   -> Waiting for build to generate a build number...")
    while True:
        try:
            queue_item = server.get_queue_item(queue_id)
            if 'executable' in queue_item:
                build_number = queue_item['executable']['number']
                print(f"   -> Build started. Build Number: {build_number}")
                return build_number
            if queue_item.get('cancelled'):
                print("   -> [ERROR] Build was cancelled in the queue.")
                sys.exit(1)
        except Exception as e:
            print(f"   -> Error checking queue: {e}")
        time.sleep(2)

def wait_for_completion(server, job_name, build_number):
    print(f"2. [ACTION] Waiting for Build #{build_number} to complete...")
    while True:
        try:
            build_info = server.get_build_info(job_name, build_number)
            if not build_info['building']:
                result = build_info['result']
                print(f"   -> Build finished. Result: {result}")
                return result
        except Exception as e:
            print(f"   -> Polling error: {e}")
        time.sleep(5)

def verify_artifact_exists(server, job_name, build_number, filename):
    print(f"\n3. [TEST] Artifact Generation Check")
    print(f"   -> Looking for artifact: '{filename}'")
    try:
        build_info = server.get_build_info(job_name, build_number)
        artifacts = build_info.get('artifacts', [])
        
        for artifact in artifacts:
            if artifact['fileName'] == filename:
                print(f"   -> [PASS] Artifact '{filename}' was generated successfully.")
                return artifact
        
        print(f"   -> [FAIL] Artifact '{filename}' NOT found in build.")
        return None
    except Exception as e:
        print(f"   -> [ERROR] Failed to fetch artifacts: {e}")
        return None

def verify_artifact_content(server, job_name, build_number, artifact_path, expected_text):
    print(f"\n4. [TEST] Artifact Content Access Check")
    print(f"   -> Downloading artifact to verify content...")
    try:
        artifact_content = server.get_build_artifact(job_name, build_number, artifact_path)
        text_content = artifact_content.decode('utf-8')
        
        if expected_text in text_content:
            print(f"   -> Found expected text: '{expected_text}'")
            print(f"   -> [PASS] Content verification successful.")
            return True
        else:
            print(f"   -> [FAIL] Text '{expected_text}' NOT found.")
            print(f"   -> Actual Content: {text_content}")
            return False
    except Exception as e:
        print(f"   -> [ERROR] Could not read artifact content: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Jenkins Plugin Integration Test Suite")
    parser.add_argument("--url", required=True, help="Jenkins Server URL")
    parser.add_argument("--user", required=True, help="Jenkins User ID")
    parser.add_argument("--token", required=True, help="Jenkins API Token")
    parser.add_argument("--job", required=True, help="Job Name (e.g., test_project)")
    
    args = parser.parse_args()

    try:
        server = jenkins.Jenkins(args.url, username=args.user, password=args.token)
        user = server.get_whoami()
        print(f"Connected to Jenkins as {user['fullName']}")
        print("=========================================")
        print("STARTING SEQUENTIAL INTEGRATION TESTS")
        print("=========================================")

        queue_id = trigger_build(server, args.job)
        build_number = get_build_number(server, queue_id)
        result = wait_for_completion(server, args.job, build_number)

        if result != 'SUCCESS':
            print(f"\n[CRITICAL FAIL] Build failed with status {result}. Stopping tests.")
            sys.exit(1)
        else:
            print(f"   -> [PASS] Basic Build Success")

      
        artifact_obj = verify_artifact_exists(server, args.job, build_number, TEST_CONFIG["ARTIFACT_NAME"])
        
        if not artifact_obj:
            print("\n[CRITICAL FAIL] Artifact generation failed. Stopping tests.")
            sys.exit(1)

    
        content_ok = verify_artifact_content(server, args.job, build_number, artifact_obj['relativePath'], TEST_CONFIG["EXPECTED_CONTENT"])

        if not content_ok:
            print("\n[CRITICAL FAIL] Artifact content is incorrect.")
            sys.exit(1)

        print("\n=========================================")
        print("ALL TESTS PASSED SUCCESSFULLY")
        print("=========================================")
        sys.exit(0)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()