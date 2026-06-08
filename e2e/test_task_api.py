import requests
import json
import time
import os
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:9541/api/v1"
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "password"  # Using the corrected password
SCRIPT_DIR = Path(__file__).resolve().parent

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg):
    print(f"{Color.GREEN}[SUCCESS] {msg}{Color.RESET}")

def print_error(msg):
    print(f"{Color.RED}[ERROR] {msg}{Color.RESET}")

def print_info(msg):
    print(f"{Color.BLUE}[INFO] {msg}{Color.RESET}")

class TaskApiTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.project_id = None
        self.file_id = None
        self.directory_id = None
        self.task_id = None

    def login(self):
        print_info("Logging in as Admin...")
        try:
            response = self.session.post(f"{BASE_URL}/users/login", json={
                "username": ADMIN_USERNAME,
                "password": ADMIN_PASSWORD
            })
            if response.status_code == 200:
                data = response.json().get("Data", {})
                self.user_id = data.get("userId")  # Corrected from "Id" to "userId" based on UserLoginResponse
                self.token = data.get("token")
                print_success(f"Login successful. UserID: {self.user_id}")
                return True
            else:
                print_error(f"Login failed: {response.text}")
                return False
        except Exception as e:
            print_error(f"Login exception: {e}")
            return False

    def setup_project_and_file(self):
        print_info("Setting up Project, Directory, and File...")
        headers = {"user-id": self.user_id}
        
        # 1. Create Project
        try:
            resp = self.session.post(f"{BASE_URL}/projects/create", json={
                "ProjectName": f"E2E_Task_Project_{int(time.time())}",
                "Description": "Project for Task E2E Test"
            }, headers=headers)
            if resp.status_code == 200:
                self.project_id = resp.json()["Data"]["ProjectId"]
                print_success(f"Project created: {self.project_id}")
            else:
                print_error(f"Create project failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Create project exception: {e}")
            return False

        # 2. Create Directory
        try:
            headers["project-id"] = self.project_id
            resp = self.session.post(f"{BASE_URL}/directories/create", json={
                "ParentDirectoryId": None,
                "Name": "TaskTestDir"
            }, headers=headers)
            if resp.status_code == 200:
                self.directory_id = resp.json()["Data"]["DirId"]
                print_success(f"Directory created: {self.directory_id}")
            else:
                print_error(f"Create directory failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Create directory exception: {e}")
            return False

        # 3. Upload File
        try:
            image_path = SCRIPT_DIR / "defect_img_1.bmp"
            if not image_path.exists():
                print_error(f"Test image not found: {image_path}")
                return False

            # Param name must be 'File' (capital F) as per FileController
            with image_path.open('rb') as f:
                files = {'File': (image_path.name, f, 'image/bmp')}

                # directory-id must be in header
                headers["directory-id"] = self.directory_id

                resp = self.session.post(f"{BASE_URL}/files/upload", files=files, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json().get("Data")
                # Correct parsing logic for FileUploadResponse
                success_files = data.get("SuccessFiles")
                if success_files and len(success_files) > 0:
                    self.file_id = success_files[0]["FileId"]
                    print_success(f"File uploaded: {self.file_id}")
                    return True
                else:
                    print_error(f"Upload returned success but no SuccessFiles found: {data}")
                    return False
            else:
                print_error(f"Upload file failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Upload file exception: {e}")
            if os.path.exists("test_task_image.jpg"):
                os.remove("test_task_image.jpg")
            return False

    def test_submit_task(self):
        print_info("Testing Submit Task...")
        headers = {
            "user-id": self.user_id,
            "project-id": self.project_id
        }
        
        payload = {
            "Name": "E2E Auto Task",
            "Description": "Testing task submission",
            "AlgorithmType": "object-detection",
            "SelectedFiles": [{"FileId": self.file_id}],
            "DirectoryIds": [] # Optionally test directory expansion
        }
        
        try:
            resp = self.session.post(f"{BASE_URL}/tasks/submit", json=payload, headers=headers)
            if resp.status_code == 200:
                self.task_id = resp.json()["Data"]["TaskId"]  # Correct key is TaskId, not Id
                print_success(f"Task submitted successfully. TaskID: {self.task_id}")
                return True
            else:
                print_error(f"Submit task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Submit task exception: {e}")
            return False

    def wait_for_task_completion(self):
        print_info("Waiting for task completion...")
        headers = {
            "user-id": self.user_id,
            "project-id": self.project_id
        }
        
        max_retries = 20
        for i in range(max_retries):
            try:
                resp = self.session.get(f"{BASE_URL}/tasks/{self.task_id}/status", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()["Data"]
                    status = data["Status"]
                    progress = data["Progress"]
                    print_info(f"Task Status: {status}, Progress: {progress}%")
                    
                    if status == "completed":
                        print_success("Task completed!")
                        # Verify Report Content (JSON)
                        report_content = data.get("TaskReport")
                        if report_content:
                            try:
                                json_report = json.loads(report_content)
                                if isinstance(json_report, list) and len(json_report) > 0:
                                    print_success(f"Task Report verified: Valid JSON array with {len(json_report)} items.")
                                    # Print details of the first result for verification
                                    print_info(f"Report Content (First Item): {json.dumps(json_report[0], indent=2, ensure_ascii=False)}")
                                else:
                                    print_error(f"Task Report invalid format: {report_content[:100]}...")
                                    return False
                            except json.JSONDecodeError:
                                print_error(f"Task Report is not valid JSON: {report_content[:100]}...")
                                return False
                        else:
                            print_error("Task Report is empty/null")
                            return False
                        return True
                    elif status == "failed":
                        print_error(f"Task failed: {data.get('ErrorMessage')}")
                        return False
                else:
                    print_error(f"Get status failed: {resp.text}")
            except Exception as e:
                print_error(f"Get status exception: {e}")
            
            time.sleep(1)
        
        print_error("Task timed out")
        return False

    def test_archive_and_restart(self):
        print_info("Testing Archive and Restart Logic...")
        headers = {
            "user-id": self.user_id,
            "project-id": self.project_id
        }

        # 1. Archive Task
        try:
            resp = self.session.put(f"{BASE_URL}/tasks/{self.task_id}/archive?archived=true", headers=headers)
            if resp.status_code == 200:
                print_success("Task archived.")
            else:
                print_error(f"Archive task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Archive task exception: {e}")
            return False

        # 2. Try to Restart (Should Fail)
        try:
            resp = self.session.post(f"{BASE_URL}/tasks/{self.task_id}/restart", headers=headers)
            if resp.status_code != 200: # Assuming 500 or 400 for logic error
                print_success("Restarting archived task failed as expected.")
            else:
                print_error("Restarting archived task SUCCEEDED (Unexpected).")
                return False
        except Exception:
            pass # Exception might occur, which is also fine

        # 3. Un-archive Task
        try:
            resp = self.session.put(f"{BASE_URL}/tasks/{self.task_id}/archive?archived=false", headers=headers)
            if resp.status_code == 200:
                print_success("Task un-archived.")
            else:
                print_error(f"Un-archive task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Un-archive task exception: {e}")
            return False

        # 4. Restart Task (Should Success)
        try:
            resp = self.session.post(f"{BASE_URL}/tasks/{self.task_id}/restart", headers=headers)
            if resp.status_code == 200:
                print_success("Task restarted successfully.")
                # Verify status is pending
                status_resp = self.session.get(f"{BASE_URL}/tasks/{self.task_id}/status", headers=headers)
                status = status_resp.json()["Data"]["Status"]
                if status == "pending" or status == "processing":
                    print_success(f"Restarted task status verified: {status}")
                    return True
                else:
                    print_error(f"Restarted task status incorrect: {status}")
                    return False
            else:
                print_error(f"Restart task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Restart task exception: {e}")
            return False

    def test_delete_task(self):
        print_info("Testing Delete Task...")
        headers = {
            "user-id": self.user_id,
            "project-id": self.project_id
        }
        
        try:
            resp = self.session.delete(f"{BASE_URL}/tasks/{self.task_id}", headers=headers)
            if resp.status_code == 200:
                print_success("Task deleted successfully.")
                
                # Verify 404
                check_resp = self.session.get(f"{BASE_URL}/tasks/{self.task_id}/status", headers=headers)
                if check_resp.status_code == 404 or check_resp.status_code == 500: # 500 might be returned by global handler for entity not found
                    print_success("Task 404 verified.")
                    return True
                else:
                    print_error(f"Task still exists after delete: {check_resp.status_code}")
                    return False
            else:
                print_error(f"Delete task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Delete task exception: {e}")
            return False

    def run(self):
        if not self.login(): return False
        if not self.setup_project_and_file(): return False
        if not self.test_submit_task(): return False
        if not self.wait_for_task_completion(): return False
        if not self.test_archive_and_restart(): return False
        # Wait for restarted task to finish (optional, but good for cleanup stability)
        if not self.wait_for_task_completion(): return False
        if not self.test_delete_task(): return False
        
        print(f"\n{Color.GREEN}=== ALL TASK E2E TESTS PASSED ==={Color.RESET}")
        return True

def test_task_api_flow():
    tester = TaskApiTester()
    assert tester.run()

if __name__ == "__main__":
    tester = TaskApiTester()
    sys.exit(0 if tester.run() else 1)
