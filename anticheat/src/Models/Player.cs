using anticheat.Converters;
using anticheat.Enums;
using Newtonsoft.Json;

namespace anticheat.Models;

internal class Player
{
    [JsonProperty("id")]
    public ulong Id { get; private set; }

    [JsonProperty("name")]
    public string? Name { get; private set; }

    [JsonProperty("safe_name")]
    public string? SafeName { get; private set; }

    [JsonProperty("priv")]
    public Privileges Privileges { get; private set; }

    [JsonProperty("stats")]
    [JsonConverter(typeof(PlayerStatsConverter))]
    public Dictionary<GameMode, ModeData> Stats { get; private set; } = null!;

    public override string ToString()
    {
        return $"<{Name} ({Id})>";
    }

    public bool HasPrivileges(Privileges privileges) => (Privileges & privileges) == privileges;
}
