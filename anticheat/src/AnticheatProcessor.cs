
using anticheat.Checks;
using anticheat.Enums;
using anticheat.Models;

namespace anticheat;

internal class AnticheatProcessor
{
    private ScoreQueue _queue;

    private ICheck[] _checks;

    public AnticheatProcessor(ScoreQueue queue, ICheck[] checks)
    {
        _queue = queue;
        _checks = checks;
    }

    private bool IsScoreEligible(Score score)
    {
        Program.Log(score.Player.Privileges.ToString());
        Program.Log(((int)Privileges.Whitelisted).ToString());

        Program.Log($"{score.Player.Privileges} & {Privileges.Whitelisted} = {score.Player.Privileges & Privileges.Whitelisted} which is != {((int)Privileges.Whitelisted)}");

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

            foreach (ICheck check in _checks)
            {
                try
                {
                    CheckResult result = check.PerformCheck(score);

                    Program.Log($"Ran check {check.GetType().Name} on {score}, Result: {result}", debug: true);

                    // TODO: act on restriction etc. here
                    if (result.Action == CheckResultAction.Restrict)
                        Program.Log($"Issued restriction on player {score.Player} with reason '{result.Statement}' through score {score}", ConsoleColor.Green);
                }
                catch (Exception ex)
                {
                    Program.Log($"An error occured while performing check {check.GetType().Name} on score with ID {score}:", ConsoleColor.Red);
                    Program.Log(ex.Message, ConsoleColor.Red);
                }
            }
        }
    }
}