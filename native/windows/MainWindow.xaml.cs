using System.Diagnostics;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;
using Windows.UI;

namespace ModelDock;

public sealed partial class MainWindow : Window
{
    private readonly BackendClient _backend = new();
    private Snapshot? _snapshot;
    private bool _updatingControls;
    private bool _busy;

    public MainWindow()
    {
        try
        {
            InitializeComponent();
            try
            {
                if (Microsoft.UI.Composition.SystemBackdrops.MicaController.IsSupported())
                    SystemBackdrop = new MicaBackdrop();
            }
            catch { }
            ConfigureWindow();
            Activated += async (_, _) =>
            {
                if (_snapshot is null) await RefreshAsync();
            };
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(Path.GetTempPath(), "ModelDock-startup-error.txt"), error.ToString());
            throw;
        }
    }

    private void ConfigureWindow()
    {
        var handle = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var id = Win32Interop.GetWindowIdFromWindow(handle);
        var appWindow = AppWindow.GetFromWindowId(id);
        appWindow.Resize(new SizeInt32(1320, 820));
        var icon = Path.Combine(AppContext.BaseDirectory, "Assets", "app_icon.ico");
        if (File.Exists(icon)) appWindow.SetIcon(icon);
    }

    public void ShowError(string message)
    {
        NoticeBar.Severity = InfoBarSeverity.Error;
        NoticeBar.Title = "操作失败";
        NoticeBar.Message = message;
        NoticeBar.IsOpen = true;
    }

    private void ShowNotice(string message)
    {
        NoticeBar.Severity = InfoBarSeverity.Success;
        NoticeBar.Title = "ModelDock";
        NoticeBar.Message = message;
        NoticeBar.IsOpen = true;
    }

    private async Task RefreshAsync()
    {
        if (_busy) return;
        await WithBusyAsync(async () =>
        {
            _snapshot = await _backend.CallAsync<Snapshot>("snapshot");
            RenderSnapshot();
        });
    }

    private async Task WithBusyAsync(Func<Task> operation)
    {
        if (_busy) return;
        _busy = true;
        BusyRing.IsActive = true;
        RootGrid.IsHitTestVisible = false;
        try { await operation(); }
        catch (Exception error) { ShowError(error.Message); }
        finally
        {
            RootGrid.IsHitTestVisible = true;
            BusyRing.IsActive = false;
            _busy = false;
        }
    }

    private async Task RunAsync<T>(string command, object payload, string? success = null)
    {
        await WithBusyAsync(async () =>
        {
            await _backend.CallAsync<T>(command, payload);
            _snapshot = await _backend.CallAsync<Snapshot>("snapshot");
            RenderSnapshot();
            if (!string.IsNullOrWhiteSpace(success)) ShowNotice(success);
        });
    }

    private void RenderSnapshot()
    {
        if (_snapshot is null) return;
        var state = _snapshot;
        _updatingControls = true;
        try
        {
            ModeTitle.Text = state.Account.Mode;
            ModeBadgeText.Text = state.Account.Mode;
            ModeDescription.Text = state.Account.ModeKey == "pure_official"
                ? "Codex 直接使用官方 provider，本地网关保持停止。"
                : "Codex 通过本地网关同时使用官方订阅和第三方模型。";

            GatewayStatusText.Text = state.Gateway.Responding ? "运行中" : state.Gateway.Running ? "启动中" : "已停止";
            GatewayStatusIcon.Foreground = new SolidColorBrush(state.Gateway.Responding ? Colors.LimeGreen : Colors.Gray);
            GatewayUrlText.Text = "地址  " + state.Gateway.Url;
            GatewayModelsText.Text = $"模型数量  {state.Gateway.Models.Count}";
            CodexStatusText.Text = state.Codex.Running ? "运行中" : "已停止";
            CodexStatusIcon.Foreground = new SolidColorBrush(state.Codex.Running ? Colors.LimeGreen : Colors.Gray);
            CodexProcessesText.Text = $"进程数  {state.Codex.Count}";

            AccountEmailText.Text = state.Account.Email;
            AccountPlanText.Text = state.Account.Plan + "（本机最新凭据返回）";
            AccountRefreshText.Text = state.Account.RefreshedAt;
            ThirdPartyCountText.Text = state.Account.ThirdPartyCount.ToString();

            ModelsList.ItemsSource = null;
            ModelsList.ItemsSource = state.Models.OrderBy(item => item.Order).ToList();
            RestoresList.ItemsSource = null;
            RestoresList.ItemsSource = state.RestorePoints;

            LoginStatusText.Text = $"当前模式：{state.Account.Mode}\n账号：{state.Account.Email}    套餐：{state.Account.Plan}\n实际 provider：{state.Provider.ModelProvider}";
            ConversationText.Text = $"活动 {state.Conversation.ActiveSessions}    归档 {state.Conversation.ArchivedSessions}    侧栏索引 {state.Conversation.IndexedThreads}    快照 {state.Conversation.Snapshots}";
            PortBox.Value = state.Port;
            AutostartToggle.IsOn = state.Autostart is "ready" or "running";
            AboutVersionText.Text = state.Version + " · ModelDock";
            for (var index = 0; index < ModeCombo.Items.Count; index++)
            {
                if (ModeCombo.Items[index] is ComboBoxItem item && (item.Tag?.ToString() ?? "") == state.Account.ModeKey)
                {
                    ModeCombo.SelectedIndex = index;
                    break;
                }
            }
        }
        finally { _updatingControls = false; }
    }

    private void Navigation_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItemContainer as NavigationViewItem)?.Tag?.ToString() ?? "home";
        HomePage.Visibility = tag == "home" ? Visibility.Visible : Visibility.Collapsed;
        ModelsPage.Visibility = tag == "models" ? Visibility.Visible : Visibility.Collapsed;
        RestoresPage.Visibility = tag == "restores" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshAsync();

    private async void GatewayAction_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button button) await RunAsync<ActionResult>("gateway_action", new { action = button.Tag?.ToString() });
    }

    private async void CodexAction_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button button) await RunAsync<ActionResult>("codex_action", new { action = button.Tag?.ToString() });
    }

    private ModelEntry? SelectedModel => ModelsList.SelectedItem as ModelEntry;

    private async void AddModel_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new ModelEditorDialog(_backend, null) { XamlRoot = RootGrid.XamlRoot };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary && dialog.Payload is not null)
            await RunAsync<ActionResult>("add_model", dialog.Payload, "模型已添加。");
    }

    private async void EditModel_Click(object sender, RoutedEventArgs e) => await EditSelectedModelAsync();
    private async void ModelsList_DoubleTapped(object sender, DoubleTappedRoutedEventArgs e) => await EditSelectedModelAsync();

    private async Task EditSelectedModelAsync()
    {
        var selected = SelectedModel;
        if (selected is null || selected.BuiltIn) return;
        var dialog = new ModelEditorDialog(_backend, selected) { XamlRoot = RootGrid.XamlRoot };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary && dialog.Payload is not null)
        {
            dialog.Payload["number"] = selected.Number;
            await RunAsync<ActionResult>("modify_model", dialog.Payload, "模型已修改。");
        }
    }

    private async void MoveModel_Click(object sender, RoutedEventArgs e)
    {
        var selected = SelectedModel;
        if (selected is null || selected.BuiltIn || sender is not Button button) return;
        var direction = int.Parse(button.Tag?.ToString() ?? "0");
        await RunAsync<MoveResult>("move_model", new { number = selected.Number, direction });
    }

    private async void DeleteModel_Click(object sender, RoutedEventArgs e)
    {
        var selected = SelectedModel;
        if (selected is null || selected.BuiltIn) return;
        var confirm = new ContentDialog
        {
            XamlRoot = RootGrid.XamlRoot,
            Title = "删除模型？",
            Content = $"将删除“{selected.DisplayName}”，序号不会被其他模型占用。",
            PrimaryButtonText = "删除",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Close
        };
        if (await confirm.ShowAsync() == ContentDialogResult.Primary)
            await RunAsync<ActionResult>("remove_model", new { number = selected.Number }, "模型已删除。");
    }

    private async void CreateRestore_Click(object sender, RoutedEventArgs e)
    {
        var name = new TextBox { Header = "名称", PlaceholderText = "例如：调整模型前" };
        var notes = new TextBox { Header = "备注", AcceptsReturn = true, Height = 90 };
        var panel = new StackPanel { Spacing = 12 };
        panel.Children.Add(name); panel.Children.Add(notes);
        var dialog = new ContentDialog { XamlRoot = RootGrid.XamlRoot, Title = "创建手动回退点", Content = panel, PrimaryButtonText = "创建", CloseButtonText = "取消" };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary)
            await RunAsync<object>("create_restore", new { name = name.Text, notes = notes.Text }, "回退点已创建。");
    }

    private async void Restore_Click(object sender, RoutedEventArgs e)
    {
        if (RestoresList.SelectedItem is not RestorePoint selected) return;
        var dialog = new ContentDialog { XamlRoot = RootGrid.XamlRoot, Title = "恢复回退点？", Content = selected.Name, PrimaryButtonText = "恢复", CloseButtonText = "取消" };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary)
            await RunAsync<ActionResult>("restore", new { id = selected.Id }, "回退点恢复完成。");
    }

    private async void ModeCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_updatingControls || ModeCombo.SelectedItem is not ComboBoxItem item) return;
        var mode = item.Tag?.ToString();
        if (!string.IsNullOrWhiteSpace(mode)) await RunAsync<MessageResult>("switch_mode", new { mode }, "模式切换完成。");
    }

    private async void Login_Click(object sender, RoutedEventArgs e) => await RunAsync<ActionResult>("login", new { device = false }, "已启动浏览器授权，请完成登录。");

    private void Usage_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(new ProcessStartInfo("https://chatgpt.com/codex/settings/usage") { UseShellExecute = true });
    }

    private async void ConversationSnapshot_Click(object sender, RoutedEventArgs e) => await RunAsync<ActionResult>("conversation_snapshot", new { }, "会话索引快照已创建。");
    private async void ConversationRepair_Click(object sender, RoutedEventArgs e) => await RunAsync<ActionResult>("conversation_repair", new { }, "会话列表修复完成。");

    private async void AutostartToggle_Toggled(object sender, RoutedEventArgs e)
    {
        if (_updatingControls) return;
        await RunAsync<ActionResult>("autostart", new { enabled = AutostartToggle.IsOn });
    }

    private async void ApplyPort_Click(object sender, RoutedEventArgs e)
    {
        if (double.IsNaN(PortBox.Value) || PortBox.Value is < 1 or > 65535) { ShowError("端口必须是 1–65535 的整数。"); return; }
        await RunAsync<ActionResult>("set_port", new { port = (int)PortBox.Value }, "端口已更新。");
    }
}
