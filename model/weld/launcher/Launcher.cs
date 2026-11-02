using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace AIVisionLauncher
{
    static class Program
    {
        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                SetProcessDPIAware();
            }
            catch { }

            try
            {
                string exeDir = AppDomain.CurrentDomain.BaseDirectory;
                string weldDir = FindWeldDirectory(exeDir);

                if (string.IsNullOrEmpty(weldDir) || !Directory.Exists(weldDir))
                {
                    MessageBox.Show(
                        "未能找到 AIVision 核心模块目录 (model/weld)。\n请确保程序放置在项目根目录或 model/weld 目录下。",
                        "AIVision 启动错误",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return;
                }

                string pythonPath = FindPythonExecutable(weldDir);
                if (string.IsNullOrEmpty(pythonPath))
                {
                    MessageBox.Show(
                        "未找到合适的 Python 环境 (需要包含 PyTorch/PyQt6 的环境，如 py11)。\n\n请确认已安装 Conda 环境并命名为 py11，或在系统环境变量中配置 Python。",
                        "AIVision 环境缺失",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                    return;
                }

                LaunchApplication(pythonPath, weldDir, args);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "启动时发生异常:\n\n" + ex.Message + "\n\n" + ex.StackTrace,
                    "AIVision 致命错误",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
        }

        static string FindWeldDirectory(string startDir)
        {
            // 候选 1: 当前目录即 weld 目录
            if (File.Exists(Path.Combine(startDir, "desktop", "app.py")))
                return startDir;

            // 候选 2: 当前目录是根目录，model/weld 在子目录
            string subWeld = Path.Combine(startDir, "model", "weld");
            if (File.Exists(Path.Combine(subWeld, "desktop", "app.py")))
                return subWeld;

            // 候选 3: 上级目录中的 model/weld
            try
            {
                string parent = Path.GetDirectoryName(Path.GetDirectoryName(startDir.TrimEnd(Path.DirectorySeparatorChar)));
                if (!string.IsNullOrEmpty(parent))
                {
                    string parentWeld = Path.Combine(parent, "model", "weld");
                    if (File.Exists(Path.Combine(parentWeld, "desktop", "app.py")))
                        return parentWeld;
                }
            }
            catch { }

            // 备选固定绝对路径
            if (Directory.Exists(@"I:\项目\AIVision\model\weld"))
                return @"I:\项目\AIVision\model\weld";

            return null;
        }

        static string FindPythonExecutable(string weldDir)
        {
            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            var candidates = new List<string>
            {
                // 1. 本机专门配置的 py11 环境（包含完整 PyTorch GPU/CUDA/Paddle）
                @"C:\Users\lucas\.conda\envs\py11\python.exe",
                Path.Combine(userProfile, @".conda\envs\py11\python.exe"),
                Path.Combine(userProfile, @"miniconda3\envs\py11\python.exe"),
                Path.Combine(userProfile, @"anaconda3\envs\py11\python.exe"),

                // 2. 项目内嵌的独立运行包（如有）
                Path.Combine(weldDir, @"python\python.exe"),
                Path.Combine(weldDir, @"env\python.exe"),
                Path.Combine(weldDir, @"py11\python.exe"),

                // 3. 环境变量中的 CONDA_PREFIX
                Environment.GetEnvironmentVariable("CONDA_PREFIX") != null
                    ? Path.Combine(Environment.GetEnvironmentVariable("CONDA_PREFIX"), "python.exe")
                    : null
            };

            foreach (var path in candidates)
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                    return path;
            }

            // 4. 扫描注册表或 where python
            string wherePath = GetCommandOutput("where python");
            if (!string.IsNullOrEmpty(wherePath))
            {
                string[] lines = wherePath.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (var line in lines)
                {
                    string trimmed = line.Trim();
                    if (File.Exists(trimmed))
                        return trimmed;
                }
            }

            return null;
        }

        static string GetCommandOutput(string command)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c " + command)
                {
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                using (Process proc = Process.Start(psi))
                {
                    string output = proc.StandardOutput.ReadToEnd();
                    proc.WaitForExit(1000);
                    return output;
                }
            }
            catch
            {
                return null;
            }
        }

        static void LaunchApplication(string pythonPath, string weldDir, string[] args)
        {
            string iqidDetSrc = Path.Combine(weldDir, "IQIDDET", "src");
            string iqidDet = Path.Combine(weldDir, "IQIDDET");
            string extraPath = string.Format("{0};{1};{2}", iqidDetSrc, iqidDet, weldDir);

            string currentPythonPath = Environment.GetEnvironmentVariable("PYTHONPATH") ?? "";
            string newPythonPath = string.IsNullOrEmpty(currentPythonPath)
                ? extraPath
                : extraPath + ";" + currentPythonPath;

            StringBuilder argBuilder = new StringBuilder();
            argBuilder.Append("-m desktop.app");
            if (args != null && args.Length > 0)
            {
                foreach (var a in args)
                {
                    argBuilder.Append(" \"").Append(a.Replace("\"", "\\\"")).Append("\"");
                }
            }

            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonPath,
                Arguments = argBuilder.ToString(),
                WorkingDirectory = weldDir,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true
            };

            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
            psi.EnvironmentVariables["PYTHONPATH"] = newPythonPath;

            DateTime startTime = DateTime.Now;
            StringBuilder errorOutput = new StringBuilder();

            using (Process process = new Process())
            {
                process.StartInfo = psi;
                process.ErrorDataReceived += (s, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        lock (errorOutput)
                        {
                            errorOutput.AppendLine(e.Data);
                        }
                    }
                };

                process.Start();
                process.BeginErrorReadLine();

                // 等待进程结束
                process.WaitForExit();

                TimeSpan runDuration = DateTime.Now - startTime;
                int exitCode = process.ExitCode;

                // 如果退出码非 0，且在短时间内崩溃，弹出错误提示
                if (exitCode != 0 && runDuration.TotalSeconds < 30)
                {
                    string errors = errorOutput.ToString().Trim();
                    if (string.IsNullOrEmpty(errors))
                    {
                        errors = "程序异常退出，退出代码: " + exitCode;
                    }

                    MessageBox.Show(
                        "AIVision 运行时发生错误并退出:\n\n" + errors,
                        "AIVision 错误提示",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                }
            }
        }
    }
}
