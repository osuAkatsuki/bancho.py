using Newtonsoft.Json;

namespace anticheat.Models;

internal class ModeData
{
    [JsonProperty("tscore")]
    public ulong TotalScore { get; private set; }

    [JsonProperty("rscore")]
    public ulong RankedScore { get; private set; }

    [JsonProperty("pp")]
    public int TotalPP { get; private set; }

    [JsonProperty("acc")]
    public float Accuracy { get; private set; }

    [JsonProperty("plays")]
    public int Plays { get; private set; }

    [JsonProperty("playtime")]
    public int PlayTime { get; private set; }

    [JsonProperty("max_combo")]
    public int MaxCombo { get; private set; }

    [JsonProperty("total_hits")]
    public int TotalHits { get; private set; }

    [JsonProperty("rank")]
    public int Rank { get; private set; }
}