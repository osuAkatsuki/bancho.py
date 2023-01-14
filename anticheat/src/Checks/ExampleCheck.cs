using anticheat.Enums;
using anticheat.Models;

namespace anticheat.Checks;

internal class ExampleCheck : Check
{
    public override CheckResult PerformCheck(Score score)
    {
        if (score.Mode == GameMode.VN_STD && score.PP >= 1500)
          return Restrict("Exceeded the PP limit of 1500pp");

        return NoAction;
    }
}
