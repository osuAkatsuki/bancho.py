using anticheat.Checks;

namespace anticheat.Models;

internal class AnticheatProcessorConfiguration
{
    public ScoreQueue Queue { get; }

    public Check[] Checks { get; }

    public bool IncludeAnticheatIdentifier { get; }

    public AnticheatProcessorConfiguration(ScoreQueue queue, Check[] checks, bool includeAnticheatIdentifier)
    {
        Queue = queue;
        Checks = checks;
        IncludeAnticheatIdentifier = includeAnticheatIdentifier;
    }
}
