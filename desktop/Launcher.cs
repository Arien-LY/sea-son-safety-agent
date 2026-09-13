using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("海之子安全质量工作台")]
[assembly: System.Reflection.AssemblyVersion("0.1.0.0")]

public sealed class Settings {
    public bool Enabled = false;
    public string Model = "deepseek-v4-flash";
    public string VisionModel = "deepseek-v4-flash-vision-exp";
    public string EncryptedKey = "";
    public string EncryptedSearchKey = "";
    public string SearchKey() {
        return EncryptedSearchKey.Length == 0 ? "" : Encoding.UTF8.GetString(
            ProtectedData.Unprotect(Convert.FromBase64String(EncryptedSearchKey), null, DataProtectionScope.CurrentUser));
    }
    public void SetSearchKey(string key) {
        EncryptedSearchKey = key.Length == 0 ? "" : Convert.ToBase64String(
            ProtectedData.Protect(Encoding.UTF8.GetBytes(key), null, DataProtectionScope.CurrentUser));
    }
    public string Key() {
        return EncryptedKey.Length == 0 ? "" : Encoding.UTF8.GetString(
            ProtectedData.Unprotect(Convert.FromBase64String(EncryptedKey), null, DataProtectionScope.CurrentUser));
    }
    public void SetKey(string key) {
        EncryptedKey = key.Length == 0 ? "" : Convert.ToBase64String(
            ProtectedData.Protect(Encoding.UTF8.GetBytes(key), null, DataProtectionScope.CurrentUser));
    }
}

public sealed class Host : IDisposable {
    Process child;
    public string Url;
    public void Start(Settings settings, string data) {
        Stop();
        Directory.CreateDirectory(data);
        var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start(); int port = ((IPEndPoint)probe.LocalEndpoint).Port; probe.Stop();
        Url = "http://127.0.0.1:" + port;
        string root = AppDomain.CurrentDomain.BaseDirectory;
        var info = new ProcessStartInfo(Path.Combine(root, "_internal", "python", "pythonw.exe"));
        info.Arguments = "-B -m desktop.server --port " + port + " --user-data \"" + data + "\"";
        info.WorkingDirectory = data;
        info.UseShellExecute = false; info.CreateNoWindow = true;
        info.RedirectStandardOutput = true; info.RedirectStandardError = true;
        // Fixed trusted endpoint; never accept endpoint, store path or Python path from a webpage.
        info.EnvironmentVariables["AGENT_MODE"] = settings.Enabled ? "real" : "mock";
        info.EnvironmentVariables["LLM_API_KEY"] = settings.Enabled ? settings.Key() : "";
        info.EnvironmentVariables["LLM_PROVIDER"] = "deepseek";
        info.EnvironmentVariables["DEEPSEEK_API_KEY"] = settings.Enabled ? settings.Key() : "";
        info.EnvironmentVariables["TAVILY_API_KEY"] = settings.Enabled ? settings.SearchKey() : "";
        info.EnvironmentVariables["LLM_MODEL"] = settings.Model;
        info.EnvironmentVariables["VISION_MODEL"] = settings.VisionModel;
        info.EnvironmentVariables["LLM_MODEL_OPTIONS"] = "";
        info.EnvironmentVariables["LLM_BASE_URL"] = "https://api.deepseek.com";
        info.EnvironmentVariables["PYTHON_DOTENV_DISABLED"] = "1";
        child = new Process(); child.StartInfo = info;
        // Drain output without persisting prompts, provider errors or secrets to disk.
        child.OutputDataReceived += delegate { }; child.ErrorDataReceived += delegate { };
        child.Start(); child.BeginOutputReadLine(); child.BeginErrorReadLine();
    }
    public bool Alive { get { return child != null && !child.HasExited; } }
    public string Read(string path) {
        var request = (HttpWebRequest)WebRequest.Create(Url + path);
        request.Proxy = null; request.Timeout = 1000;
        using (var response = request.GetResponse())
        using (var reader = new StreamReader(response.GetResponseStream())) return reader.ReadToEnd();
    }
    public bool Ready() { try { return Alive && Read("/health").Contains("ok"); } catch { return false; } }
    public void Stop() {
        if (child == null) return;
        try { if (!child.HasExited) { child.Kill(); child.WaitForExit(5000); } } finally { child.Dispose(); child = null; }
    }
    public void Dispose() { Stop(); }
}

public sealed class Workbench : Form {
    readonly string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SeaSon");
    readonly Host host = new Host();
    readonly Label status = new Label();
    readonly Button open = new Button();
    readonly System.Windows.Forms.Timer poll = new System.Windows.Forms.Timer();
    Settings settings;
    int ticks;
    bool opened;
    public Workbench() {
        Text = "海之子 · 安全质量工作台"; Size = new Size(510, 310);
        StartPosition = FormStartPosition.CenterScreen; FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; Font = new Font("Microsoft YaHei UI", 10);
        BackColor = Color.White; Icon = SystemIcons.Application;
        var title = new Label { Text = "海之子", Font = new Font(Font.FontFamily, 23, FontStyle.Bold), Left = 28, Top = 22, Width = 420, Height = 45 };
        var note = new Label { Text = "安全 · 质量 · 管理 · 后勤", Left = 30, Top = 76, Width = 430, Height = 26 };
        status.SetBounds(30, 116, 430, 45);
        open.Text = "打开工作台"; open.SetBounds(30, 177, 130, 40); open.Enabled = false;
        open.Click += delegate { OpenBrowser(); };
        var config = new Button { Text = "模型设置" }; config.SetBounds(174, 177, 130, 40);
        config.Click += delegate { Configure(); };
        var exit = new Button { Text = "退出" }; exit.SetBounds(318, 177, 130, 40); exit.Click += delegate { Close(); };
        var boundary = new Label { Text = "比赛试用版 · 数据保存在本机 · 关闭此窗口将停止服务", Left = 30, Top = 231, Width = 450, Height = 25, ForeColor = Color.DimGray, Font = new Font(Font.FontFamily, 8) };
        Controls.AddRange(new Control[] { title, note, status, open, config, exit, boundary });
        Directory.CreateDirectory(data);
        settings = LoadSettings();
        poll.Interval = 1000; poll.Tick += delegate {
            if (host.Ready()) { poll.Stop(); open.Enabled = true; status.Text = settings.Enabled ? "工作台已就绪，AI 将使用你的模型服务。" : "工作台已就绪。AI 尚未启用，可在模型设置中开启。"; if (!opened) { opened = true; OpenBrowser(); } }
            else if (++ticks >= 60 || !host.Alive) { poll.Stop(); status.Text = "启动未成功，请关闭后重试或联系软件提供者。"; }
        };
        Shown += delegate { StartService(); };
        FormClosed += delegate { poll.Stop(); host.Dispose(); };
    }
    Settings LoadSettings() {
        string path = Path.Combine(data, "settings.json");
        if (!File.Exists(path)) return new Settings();
        try { var value = new JavaScriptSerializer().Deserialize<Settings>(File.ReadAllText(path)); value.Key(); value.SearchKey(); return value; }
        catch { MessageBox.Show("无法读取本机模型设置，请重新填写。原设置文件未修改。", "海之子"); return new Settings(); }
    }
    void StartService() {
        open.Enabled = false; ticks = 0; status.Text = "正在启动工作台…";
        try { host.Start(settings, data); poll.Start(); }
        catch { status.Text = "启动失败，请确认压缩包已完整解压，并且文件没有被安全软件移除。"; }
    }
    void OpenBrowser() { try { Process.Start(new ProcessStartInfo(host.Url + "/chat") { UseShellExecute = true }); } catch { MessageBox.Show("请在浏览器打开：" + host.Url, "海之子"); } }
    void Configure() {
        using (var dialog = new Form()) {
            dialog.Text = "模型与联网设置"; dialog.Size = new Size(520, 480); dialog.Font = Font;
            dialog.StartPosition = FormStartPosition.CenterParent; dialog.FormBorderStyle = FormBorderStyle.FixedDialog; dialog.MaximizeBox = false; dialog.MinimizeBox = false;
            var enabled = new CheckBox { Text = "启用 AI（需要联网，模型服务可能收费）", Checked = settings.Enabled, Left = 24, Top = 22, Width = 450 };
            var key = new TextBox { Text = settings.Key(), UseSystemPasswordChar = true, Left = 24, Top = 87, Width = 450, MaxLength = 512 };
            var model = new TextBox { Text = settings.Model, Left = 24, Top = 150, Width = 450, MaxLength = 100 };
            var vision = new TextBox { Text = settings.VisionModel, Left = 24, Top = 213, Width = 450, MaxLength = 100 };
            var search = new TextBox { Text = settings.SearchKey(), UseSystemPasswordChar = true, Left = 24, Top = 276, Width = 450, MaxLength = 512 };
            var tip = new Label { Text = "聊天：DeepSeek；搜索：Tavily（可选，可能收费）。\n两种密钥独立加密保存。重启后可从最近聊天恢复已完成问答。", Left = 24, Top = 318, Width = 460, Height = 50 };
            var save = new Button { Text = "保存并重启", Left = 320, Top = 387, Width = 154, Height = 34 };
            save.Click += delegate {
                if (!Regex.IsMatch(model.Text.Trim(), @"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,99}\z") || !Regex.IsMatch(vision.Text.Trim(), @"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,99}\z") || (enabled.Checked && String.IsNullOrWhiteSpace(key.Text))) { MessageBox.Show("请填写有效的模型名称和密钥。", "模型设置"); return; }
                if (MessageBox.Show("确认保存设置并重启？正在生成的回复将中断；已完成聊天和已保存工单会保留，未保存申请需重新填写。", "海之子", MessageBoxButtons.OKCancel) != DialogResult.OK) return;
                try {
                    var next = new Settings { Enabled = enabled.Checked, Model = model.Text.Trim(), VisionModel = vision.Text.Trim() }; next.SetKey(key.Text.Trim()); next.SetSearchKey(search.Text.Trim());
                    string path = Path.Combine(data, "settings.json"), temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
                    File.WriteAllText(temporary, new JavaScriptSerializer().Serialize(next), new UTF8Encoding(false));
                    if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
                    settings = next; opened = false; poll.Stop(); StartService(); dialog.Close();
                } catch { MessageBox.Show("设置保存失败，请检查用户目录是否可写。", "海之子"); }
            };
            dialog.Controls.AddRange(new Control[] { enabled, key, model, vision, search, tip, save,
                new Label { Text = "DeepSeek 接口密钥", Left = 24, Top = 61, Width = 450 },
                new Label { Text = "Tavily 搜索密钥（可选）", Left = 24, Top = 250, Width = 450 },
                new Label { Text = "聊天模型", Left = 24, Top = 124, Width = 450 },
                new Label { Text = "图片模型", Left = 24, Top = 187, Width = 450 } });
            dialog.ShowDialog(this);
        }
    }
    [STAThread]
    public static int Main(string[] args) {
        if (args.Length == 2 && args[0] == "--smoke") {
            using (var check = new Host()) {
                try {
                    check.Start(new Settings(), Path.GetFullPath(args[1]));
                    for (int i = 0; i < 60 && !check.Ready(); i++) Thread.Sleep(1000);
                    if (!check.Ready()) return 1;
                    if (!check.Read("/chat").Contains("<html")) return 2;
                    if (check.Read("/api/runtime").Contains("tutorial")) return 3;
                    var sample = new Settings(); sample.SetKey("synthetic-local-test");
                    if (sample.Key() != "synthetic-local-test" || sample.EncryptedKey.Contains("synthetic")) return 4;
                    return 0;
                } catch { return 5; }
            }
        }
        bool owner;
        using (var mutex = new Mutex(true, "Local\\SeaSonWorkbench", out owner)) {
            if (!owner) { MessageBox.Show("海之子已经运行，请使用已打开的工作台窗口。", "海之子"); return 0; }
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Workbench()); mutex.ReleaseMutex();
        }
        return 0;
    }
}
