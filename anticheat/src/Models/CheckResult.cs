using anticheat.Checks;
using anticheat.Enums;

namespace anticheat.Models;

internal class CheckResult
{
    public Check Check { get; }

    public CheckResultAction Action { get; }

    public string Statement { get; }

    public CheckResult(Check check, CheckResultAction action, string statement = "")
    {
        Check = check;
        Action = action;
        Statement = statement;
    }

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