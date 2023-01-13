using anticheat.Enums;
using anticheat.Models;

namespace anticheat.Checks;

internal class ExampleCheck : Check
{
    public override CheckResult PerformCheck()
    {
        if (Score.Mode == GameMode.VanillaOsu && Score.PP >= 1500)
          return Restrict("Exceeded the PP limit of 1500pp");

        return NoAction;
    }
}
