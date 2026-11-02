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
                        "未能找到 AIVision 核心程序目录 (model/weld)。\n\n请确保解压或复制了完整的程序包。",
                        "AIVision 启动错误",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return;
                }

                string pythonPath = FindPythonExecutable(exeDir, weldDir);
                if (string.IsNullOrEmpty(pythonPath))
                {
                    MessageBox.Show(
                        "未检测到运行依赖环境。\n\n" +
                        "1. 如果是便携发布包，请确保 runtime/ 目录已随程序一同复制。\n" +
                        "2. 如果是开发调试，请确认系统已安装 py11 环境。",
                        "AIVision 依赖缺失",
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
            // 1. 同级目录即 weld 目录
            if (File.Exists(Path.Combine(startDir, "desktop", "app.py")))
                return startDir;

            // 2. 子目录 model/weld
            string subWeld = Path.Combine(startDir, "model", "weld");
            if (File.Exists(Path.Combine(subWeld, "desktop", "app.py")))
                return subWeld;

            // 3. 上级目录或项目根目录查找
            try
            {
                string parent = Path.GetDirectoryName(startDir.TrimEnd(Path.DirectorySeparatorChar));
                if (!string.IsNullOrEmpty(parent))
                {
                    string parentWeld = Path.Combine(parent, "model", "weld");
                    if (File.Exists(Path.Combine(parentWeld, "desktop", "app.py")))
                        return parentWeld;
                }
            }
            catch { }

            // 4. 开发机绝对路径备用
            if (Directory.Exists(@"I:\项目\AIVision\model\weld") && File.Exists(@"I:\项目\AIVision\model\weld\desktop\app.py"))
                return @"I:\项目\AIVision\model\weld";

            return null;
        }

        static string FindPythonExecutable(string exeDir, string weldDir)
        {
            // 最高优先级：便携包自包含独立环境 (无论拷到哪台电脑都自成一体)
            var portableCandidates = new List<string>
            {
                Path.Combine(exeDir, @"runtime\python.exe"),
                Path.Combine(exeDir, @"env\python.exe"),
                Path.Combine(exeDir, @"python\python.exe"),
                Path.Combine(weldDir, @"runtime\python.exe"),
                Path.Combine(weldDir, @"env\python.exe"),
                Path.Combine(weldDir, @"python\python.exe"),
            };

            foreach (var path in portableCandidates)
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                    return path;
            }

            // 次优先级：原开发机上的 Conda py11 环境
            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            var condaCandidates = new List<string>
            {
                @"C:\Users\lucas\.conda\envs\py11\python.exe",
                Path.Combine(userProfile, @".conda\envs\py11\python.exe"),
                Path.Combine(userProfile, @"miniconda3\envs\py11\python.exe"),
                Path.Combine(userProfile, @"anaconda3\envs\py11\python.exe"),
                Environment.GetEnvironmentVariable("CONDA_PREFIX") != null
                    ? Path.Combine(Environment.GetEnvironmentVariable("CONDA_PREFIX"), "python.exe")
                    : null
            };

            foreach (var path in condaCandidates)
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                    return path;
            }

            // 最低优先级：系统 PATH 中的 python
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
            string pythonDir = Path.GetDirectoryName(pythonPath);
            string iqidDetSrc = Path.Combine(weldDir, "IQIDDET", "src");
            string iqidDet = Path.Combine(weldDir, "IQIDDET");
            string extraPythonPath = string.Format("{0};{1};{2}", iqidDetSrc, iqidDet, weldDir);

            string currentPythonPath = Environment.GetEnvironmentVariable("PYTHONPATH") ?? "";
            string newPythonPath = string.IsNullOrEmpty(currentPythonPath)
                ? extraPythonPath
                : extraPythonPath + ";" + currentPythonPath;

            // 确保自包含环境的 DLL 和 Scripts 处于系统 PATH 最前端，确保 CUDA / Qt 加载无误
            string currentPath = Environment.GetEnvironmentVariable("PATH") ?? "";
            string runtimePaths = string.Format("{0};{1};{2};{3}",
                pythonDir,
                Path.Combine(pythonDir, "Scripts"),
                Path.Combine(pythonDir, "Library", "bin"),
                Path.Combine(pythonDir, "Lib", "site-packages", "torch", "lib"));
            string newPath = runtimePaths + ";" + currentPath;

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
            psi.EnvironmentVariables["PATH"] = newPath;

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

                process.WaitForExit();

                TimeSpan runDuration = DateTime.Now - startTime;
                int exitCode = process.ExitCode;

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
