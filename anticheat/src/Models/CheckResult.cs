using anticheat.Checks;
using anticheat.Enums;

namespace anticheat.Models;

internal class CheckResult
{
    public CheckResultAction Action { get; }

    public string Statement { get; }

    public CheckResult(CheckResultAction action, string statement = "")
    {
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
