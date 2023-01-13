using anticheat.Enums;
using anticheat.Models;

namespace anticheat.Checks;

internal abstract class Check
{
    public Score Score { get; set; } = null!;

    public abstract CheckResult PerformCheck();

    public CheckResult NoAction => new CheckResult(this, CheckResultAction.None);

    public CheckResult Restrict(string reason) => new CheckResult(this, CheckResultAction.Restrict, reason);
}