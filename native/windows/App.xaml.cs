using Microsoft.UI.Xaml;

namespace ModelDock;

public partial class App : Application
{
    public static MainWindow? MainWindowInstance { get; private set; }

    public App()
    {
        InitializeComponent();
        UnhandledException += (_, args) =>
        {
            args.Handled = true;
            MainWindowInstance?.ShowError(args.Exception.Message);
        };
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            MainWindowInstance = new MainWindow();
            MainWindowInstance.Activate();
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(Path.GetTempPath(), "ModelDock-startup-error.txt"), error.ToString());
            throw;
        }
    }
}
