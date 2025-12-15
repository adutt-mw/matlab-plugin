import jenkins
import time
import argparse
import sys

def trigger_build(server, job_name, params=None):
    """Triggers a build and returns the queue item number."""
    print(f"Triggering build for job: {job_name}")
    queue_id = server.build_job(job_name, parameters=params)
    print(f"Build triggered. Queue ID: {queue_id}")
    return queue_id

def get_build_number(server, queue_id):
    """Waits for the queue item to become a build and returns the build number."""
    print("Waiting for build to start...")
    while True:
        try:
            queue_item = server.get_queue_item(queue_id)
            if 'executable' in queue_item:
                build_number = queue_item['executable']['number']
                print(f"Build started. Build Number: {build_number}")
                return build_number
            if queue_item.get('cancelled'):
                print("Build was cancelled in the queue.")
                sys.exit(1)
        except Exception as e:
            print(f"Error checking queue: {e}")
        
        time.sleep(2)

def wait_for_build_completion(server, job_name, build_number):
    """Waits for the build to complete and returns the result."""
    print(f"Waiting for build #{build_number} to complete...")
    while True:
        try:
            build_info = server.get_build_info(job_name, build_number)
            if not build_info['building']:
                result = build_info['result']
                print(f"Build completed. Result: {result}")
                return result
        except Exception as e:
            print(f"Error checking build status: {e}")
        
        time.sleep(5)

def verify_log_substring(server, job_name, build_number, substring):
    """Verifies if a substring is present in the build logs."""
    print(f"Checking logs for substring: '{substring}'")
    try:
        logs = server.get_build_console_output(job_name, build_number)
        if substring in logs:
            print("Log Verification completed. Result: SUCCESS")
            return True
        else:
            print("Log Verification completed. Result: FAILURE")
            print("--- BEGIN BUILD LOGS ---")
            print(logs)
            print("--- END BUILD LOGS ---")
            return False
    except Exception as e:
        print(f"Error fetching logs: {e}")
        print("Log Verification completed. Result: FAILURE")
        return False

def verify_artifact(server, job_name, build_number, artifact_name, content_substring=None):
    """Verifies if an artifact exists and optionally checks its content."""
    print(f"Verifying artifact: {artifact_name}")
    try:
        build_info = server.get_build_info(job_name, build_number)
        artifacts = build_info.get('artifacts', [])
        
        found_artifact = None
        for artifact in artifacts:
            if artifact['fileName'] == artifact_name:
                found_artifact = artifact
                break
        
        if not found_artifact:
            print(f"Artifact '{artifact_name}' not found.")
            print("Artifact Verification completed. Result: FAILURE")
            return False
        
        print(f"Artifact '{artifact_name}' found.")
        
        if content_substring:
            print(f"Checking artifact content for: '{content_substring}'")
            artifact_content = server.get_build_artifact(job_name, build_number, found_artifact['relativePath'])
            # artifact_content is bytes, decode if expecting text
            try:
                text_content = artifact_content.decode('utf-8')
                if content_substring in text_content:
                    print("Artifact Content Verification completed. Result: SUCCESS")
                    return True
                else:
                    print("Artifact Content Verification completed. Result: FAILURE")
                    return False
            except UnicodeDecodeError:
                print("Artifact is not valid UTF-8 text, cannot search for substring.")
                print("Artifact Content Verification completed. Result: FAILURE")
                return False
        
        print("Artifact Verification completed. Result: SUCCESS")
        return True

    except Exception as e:
        print(f"Error verifying artifact: {e}")
        print("Artifact Verification completed. Result: FAILURE")
        return False

def verify_matlab_root(server, job_name, build_number, expected_root):
    """Verifies if the expected MATLAB root path is present in the build logs."""
    print(f"Verifying MATLAB root in logs: '{expected_root}'")
    try:
        logs = server.get_build_console_output(job_name, build_number)
        if expected_root in logs:
            print("MATLAB Root Verification completed. Result: SUCCESS")
            return True
        else:
            print("MATLAB Root Verification completed. Result: FAILURE")
            return False
    except Exception as e:
        print(f"Error fetching logs for MATLAB root verification: {e}")
        print("MATLAB Root Verification completed. Result: FAILURE")
        return False

def verify_log_substring_absent(server, job_name, build_number, substring):
    """Verifies if a substring is ABSENT in the build logs."""
    print(f"Checking logs for ABSENCE of substring: '{substring}'")
    try:
        logs = server.get_build_console_output(job_name, build_number)
        if substring not in logs:
            print("Negative Log Verification completed. Result: SUCCESS")
            return True
        else:
            print(f"Substring '{substring}' FOUND in logs (unexpected).")
            print("Negative Log Verification completed. Result: FAILURE")
            return False
    except Exception as e:
        print(f"Error fetching logs: {e}")
        print("Negative Log Verification completed. Result: FAILURE")
        return False

def main():
    parser = argparse.ArgumentParser(description="Jenkins Build Verifier")
    parser.add_argument("--url", required=True, help="Jenkins Server URL")
    parser.add_argument("--user", required=True, help="Jenkins User ID")
    parser.add_argument("--token", required=True, help="Jenkins API Token or Password")
    parser.add_argument("--job", required=True, help="Jenkins Job Name")
    parser.add_argument("--log-string", help="Substring to verify in build logs")
    parser.add_argument("--log-string-absent", help="Substring to verify is ABSENT in build logs")
    parser.add_argument("--artifact", help="Artifact filename to verify")
    parser.add_argument("--artifact-content", help="Substring to check inside the artifact")
    parser.add_argument("--matlab-root", help="Expected MATLAB root path to verify in logs")

    args = parser.parse_args()

    try:
        server = jenkins.Jenkins(args.url, username=args.user, password=args.token)
        user = server.get_whoami()
        print(f"Connected to Jenkins version {server.get_version()} as {user['fullName']}")

        # 1. Trigger Build
        queue_id = trigger_build(server, args.job)
        
        # 2. Get Build Number
        build_number = get_build_number(server, queue_id)
        
        # 3. Verify Status
        result = wait_for_build_completion(server, args.job, build_number)
        if result != 'SUCCESS':
            print(f"Warning: Build finished with status {result}")
        
        # 4. Verify Log Substring (Presence)
        print("\n--- Log Verification (Presence) ---")
        if args.log_string:
            if not verify_log_substring(server, args.job, build_number, args.log_string):
                print("Log verification failed.")
                sys.exit(1)
        else:
            print("Skipping log verification (no --log-string provided).")

        # 5. Verify Log Substring (Absence)
        print("\n--- Log Verification (Absence) ---")
        if args.log_string_absent:
            if not verify_log_substring_absent(server, args.job, build_number, args.log_string_absent):
                print("Negative log verification failed.")
                sys.exit(1)
        else:
            print("Skipping negative log verification (no --log-string-absent provided).")

        # 6. Verify MATLAB Root
        print("\n--- MATLAB Root Verification ---")
        if args.matlab_root:
            if not verify_matlab_root(server, args.job, build_number, args.matlab_root):
                print("MATLAB root verification failed.")
                sys.exit(1)
        else:
            print("Skipping MATLAB root verification (no --matlab-root provided).")
        
        # 7. Verify Artifact
        print("\n--- Artifact Verification ---")
        if args.artifact:
            if not verify_artifact(server, args.job, build_number, args.artifact, args.artifact_content):
                print("Artifact verification failed.")
                sys.exit(1)
        else:
            print("Skipping artifact verification (no --artifact provided).")

        print("\n========================================")
        print("All requested verifications passed successfully!")
        print("========================================")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
