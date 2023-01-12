
using anticheat.Checks;

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

    }
}