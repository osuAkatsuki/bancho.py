using anticheat.Models;

namespace anticheat.Checks;

internal interface ICheck
{
    public CheckResult PerformCheck(Score score);
}