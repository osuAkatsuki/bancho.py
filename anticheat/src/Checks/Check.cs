using anticheat.Enums;
using anticheat.Models;

namespace anticheat.Checks;

internal abstract class Check
{
    public abstract CheckResult PerformCheck(Score score);

    public CheckResult NoAction => new CheckResult(CheckResultAction.None);

    public CheckResult Restrict(string reason) => new CheckResult(CheckResultAction.Restrict, reason);
}
