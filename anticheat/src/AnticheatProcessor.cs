
using anticheat.Checks;
using anticheat.Enums;
using anticheat.Models;

namespace anticheat;

internal class AnticheatProcessor
{
    private ScoreQueue _queue;

    private Check[] _checks;

    private Config _config;

    public AnticheatProcessor(ScoreQueue queue, Check[] checks, Config config)
    {
        _queue = queue;
        _checks = checks;
        _config = config;
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
        // Run the anticheat's lifecycle
        while (true)
        {
            // Dequeue the next score in the queue using the blocking Dequeue() method
            Score score = _queue.Dequeue();
#if !DEBUG
            // Check whether the score is eligible to run through the checks.
            // This is done to filter out trustworthy scores so that the anticheat
            // does not have to run possibly performance-intensive checks on them
            if (!IsScoreEligible(score))
                continue;
#endif

            // Run each check on the score
            foreach (Check check in _checks)
            {
                try
                {
                    CheckResult result = check.PerformCheck(score);
                    Program.Log($"Ran check {check.GetType().Name} on {score}, Result: {result}", debug: true);

                    // Perform actions depending on the result of the check
                    if (HandleCheckResult(score, check, result))
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

    private bool HandleCheckResult(Score score, Check check, CheckResult result)
    {
        // If the check did not request any actions to be taken,
        // simply return a false signalizing that the anticheat
        // should continue running the other checks on it
        if (result.Action == CheckResultAction.None)
            return false;

        // If a restrict was requested, send the restriction to the server
        if (result.Action == CheckResultAction.Restrict)
        {
            string reason = result.Statement;
            if (_config.IncludeAnticheatIdentifier)
                reason = $"[anticheat:{check.GetType().Name.ToLower()}:{score.Id}] {reason}";

            Restrict(score.Player.Id, reason);
            Program.Log($"Issued restriction on player {score.Player} with reason '{reason}' through score {score}", ConsoleColor.Green);
        }

        return true;
    }

    private void Restrict(ulong userId, string reason)
    {
#if !DEBUG
         // TODO: Implement restriction either via endpoint or pubsub in b.py
#endif
    }
}