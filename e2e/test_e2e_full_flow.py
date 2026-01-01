import requests
import json
import time
import os
import sys

# Configuration
BASE_URL = "http://localhost:9541/api/v1"
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "password"

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

class FullFlowTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.project_id = None
        self.file_ids = []
        self.directory_id = None
        self.task_id = None
        self.test_images = [f"defect_img_{i}.bmp" for i in range(1, 6)]

    def login(self):
        print_info("Step 1: Logging in as Admin...")
        try:
            response = self.session.post(f"{BASE_URL}/users/login", json={
                "username": ADMIN_USERNAME,
                "password": ADMIN_PASSWORD
            })
            if response.status_code == 200:
                data = response.json().get("Data", {})
                self.user_id = data.get("userId")
                self.token = data.get("token")
                print_success(f"Login successful. UserID: {self.user_id}")
                return True
            else:
                print_error(f"Login failed: {response.text}")
                return False
        except Exception as e:
            print_error(f"Login exception: {e}")
            return False

    def setup_project_resources(self):
        print_info("Step 2: Setting up Project, Directory, and Files...")
        headers = {"user-id": self.user_id}
        
        # 1. Create Project
        try:
            resp = self.session.post(f"{BASE_URL}/projects/create", json={
                "ProjectName": f"E2E_Real_Defect_Test_{int(time.time())}",
                "Description": "Integration test with real defect images"
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
                "Name": "DefectSamples"
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

        # 3. Upload Files
        print_info(f"Uploading {len(self.test_images)} images...")
        for img_name in self.test_images:
            if not os.path.exists(img_name):
                print_error(f"Image {img_name} not found! Please run 'cp' commands first.")
                return False
            
            try:
                # directory-id must be in header
                headers["directory-id"] = self.directory_id
                
                with open(img_name, 'rb') as f:
                    files = {'File': (img_name, f, 'image/bmp')}
                    resp = self.session.post(f"{BASE_URL}/files/upload", files=files, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json().get("Data")
                    success_files = data.get("SuccessFiles")
                    if success_files and len(success_files) > 0:
                        fid = success_files[0]["FileId"]
                        self.file_ids.append(fid)
                        print_success(f"Uploaded {img_name}: {fid}")
                    else:
                        print_error(f"Upload failed for {img_name}: {data}")
                        return False
                else:
                    print_error(f"Upload request failed: {resp.text}")
                    return False
            except Exception as e:
                print_error(f"Upload file exception: {e}")
                return False
                
        return True

    def submit_and_monitor_task(self):
        print_info("Step 3: Submitting Inference Task...")
        headers = {
            "user-id": self.user_id,
            "project-id": self.project_id
        }
        
        payload = {
            "Name": "Defect Detection Task",
            "Description": "Testing with real defect images",
            "AlgorithmType": "weld-detection",
            "SelectedFiles": [{"FileId": fid} for fid in self.file_ids],
            "DirectoryIds": []
        }
        
        try:
            resp = self.session.post(f"{BASE_URL}/tasks/submit", json=payload, headers=headers)
            if resp.status_code == 200:
                self.task_id = resp.json()["Data"]["TaskId"]
                print_success(f"Task submitted. TaskID: {self.task_id}")
            else:
                print_error(f"Submit task failed: {resp.text}")
                return False
        except Exception as e:
            print_error(f"Submit task exception: {e}")
            return False

        # Monitor Loop
        print_info("Step 4: Monitoring Task Progress...")
        max_retries = 600 # 10 minutes
        last_progress = -1
        
        for i in range(max_retries):
            try:
                resp = self.session.get(f"{BASE_URL}/tasks/{self.task_id}/status", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()["Data"]
                    status = data["Status"]
                    progress = data.get("Progress", 0)
                    
                    if progress != last_progress:
                        bar_len = 20
                        filled = int(bar_len * progress / 100)
                        bar = '=' * filled + '-' * (bar_len - filled)
                        sys.stdout.write(f"\r[{bar}] {progress}% Status: {status}   ")
                        sys.stdout.flush()
                        last_progress = progress
                    
                    if status == "completed":
                        print("\n")
                        print_success("Task completed successfully!")
                        return self.verify_results(data)
                    elif status == "failed":
                        print("\n")
                        print_error(f"Task failed. Error Message: {data.get('ErrorMessage')}")
                        return False
                else:
                    print_error(f"Get status failed: {resp.text}")
            except Exception as e:
                print_error(f"Monitor exception: {e}")
            
            time.sleep(1)
        
        print_error("Task timed out!")
        return False

    def verify_results(self, task_data):
        print_info("Step 5: Verifying Result Format...")
        report_content = task_data.get("TaskReport")
        if not report_content:
            print_error("TaskReport field is empty")
            return False
            
        try:
            results = json.loads(report_content)
            print_info(f"Received {len(results)} result items.")
            
            total_defects_found = 0
            for idx, res in enumerate(results):
                vision_res = res.get("visionResult", {})
                metadata = vision_res.get("metadata", {})
                defects = vision_res.get("results", [])
                
                path = metadata.get("image_path", "unknown")
                num_defects = len(defects)
                total_defects_found += num_defects
                
                print(f"  [{idx+1}] File: {path.split('/')[-1]}")
                print(f"      Defects Found: {num_defects}")
                
                if num_defects > 0:
                    print(f"      First Defect: {defects[0]['strName']} (Score: {defects[0]['score']})")
                    # Check vvContour structure
                    contour = defects[0].get("vvContour")
                    if contour and isinstance(contour, list) and len(contour) > 0:
                        print(f"      Contour Points: {len(contour)}")
                    else:
                        print_error("      Invalid or missing vvContour")
            
            if total_defects_found > 0:
                print_success(f"Total defects found across all images: {total_defects_found}")
            else:
                print(f"{Color.YELLOW}[WARN] No defects detected in any image. (Check model performance or image quality){Color.RESET}")

        except json.JSONDecodeError:
            print_error("TaskReport is not valid JSON")
            return False
            
        return True

    def run(self):
        if not self.login(): return
        if not self.setup_project_resources(): return
        if not self.submit_and_monitor_task(): return
        
        print(f"\n{Color.GREEN}=== INTEGRATION TEST PASSED ==={Color.RESET}")

if __name__ == "__main__":
    tester = FullFlowTester()
    tester.run()
