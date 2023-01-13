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

    // TODO: Implement stats

    public override string ToString()
    {
        return $"<{Name} ({Id})>";
    }

    public bool HasPrivileges(Privileges privileges) => Privileges.HasFlag(privileges);
}