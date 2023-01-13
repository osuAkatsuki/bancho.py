
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

    public void Run()
    {
        while (true)
        {
            Score score = _queue.Dequeue();

            foreach (ICheck check in _checks)
            {
                try
                {
                    CheckResult result = check.PerformCheck(score);

                    Program.Log($"Ran check {check.GetType().Name} on score with ID {score.Id}, Result: {result}", debug: true);

                    // TODO: act on restriction etc. here
                    if (result.Action == CheckResultAction.Restrict)
                        Program.Log($"Issued restriction on player {score.Player} with reason '{result.Statement}'", ConsoleColor.Green);
                }
                catch (Exception ex)
                {
                    Program.Log($"An error occured while performing check {check.GetType().Name} on score with ID {score.Id}:", ConsoleColor.Red);
                    Program.Log(ex.Message, ConsoleColor.Red);
                }
            }
        }
    }
}