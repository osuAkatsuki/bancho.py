using anticheat.Enums;
using anticheat.Models;

namespace anticheat.Checks;

internal class ExampleCheck : ICheck
{
    public CheckResult PerformCheck(Score score)
    {
        if (score.Mode == GameMode.VanillaOsu && score.PP >= 1500)
          return CheckResult.Restrict("Exceeded the PP limit of 1500pp");

        return CheckResult.Clear;
    }
}
