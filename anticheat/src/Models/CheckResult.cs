using anticheat.Enums;

namespace anticheat.Models;

internal class CheckResult
{
    public CheckResultAction Action { get; }

    public string Statement { get; }

    private CheckResult(CheckResultAction action, string statement = "")
    {
        Action = action;
        Statement = statement;
    }

    public static CheckResult Clear => new CheckResult(CheckResultAction.None);

    public static CheckResult Restrict(string reason) => new CheckResult(CheckResultAction.Restrict, reason);

    public override string ToString()
    {
        switch (Action)
        {
            case CheckResultAction.None:
                return "None";

            case CheckResultAction.Restrict:
                return $"Restrict ({Statement})";

            default:
                return "Unhandled CheckResultAction";
        }
    }
}