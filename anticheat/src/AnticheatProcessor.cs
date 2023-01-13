
using anticheat.Checks;
using anticheat.Enums;
using anticheat.Models;

namespace anticheat;

internal class AnticheatProcessor
{
    private ScoreQueue _queue;

    private Check[] _checks;

    public AnticheatProcessor(ScoreQueue queue, Check[] checks)
    {
        _queue = queue;
        _checks = checks;
    }

    private bool IsScoreEligible(Score score)
    {
        // Check whether the score should run through the checks as this
        // might not be wanted if the user is already restricted or whitelisted
        if (!score.Player.HasPrivileges(Privileges.Unrestricted))
            Program.Log($"Score {score} is not eligible for checking because the player is restricted.", debug: true);
        else if (score.Player.HasPrivileges(Privileges.Whitelisted))
            Program.Log($"Score {score} is not eligible for checking because the player is whitelisted.", debug: true);
        else
            return true;

        return false;
    }

    public void Run()
    {
        while (true)
        {
            Score score = _queue.Dequeue();
            if (!IsScoreEligible(score))
                continue;

            foreach (Check check in _checks)
            {
                check.Score = score;

                try
                {
                    CheckResult result = check.PerformCheck();
                    Program.Log($"Ran check {check.GetType().Name} on {score}, Result: {result}", debug: true);

                    if (HandleCheckResult(result))
                        break;
                }
                catch (Exception ex)
                {
                    Program.Log($"An error occured while performing check {check.GetType().Name} on score with ID {score}:", ConsoleColor.Red);
                    Program.Log(ex.Message, ConsoleColor.Red);
                }
            }
        }
    }

    private bool HandleCheckResult(CheckResult result)
    {
        if (result.Action == CheckResultAction.None)
            return false;

        if (result.Action == CheckResultAction.Restrict)
        {
            string reason = $"(anticheat:{result.Check.GetType().Name}) {result.Statement}";
            Program.Log($"Issued restriction on player {result.Check.Score.Player} with reason '{reason}' through score {result.Check.Score}", ConsoleColor.Green);
        }

        return true;
    }
}