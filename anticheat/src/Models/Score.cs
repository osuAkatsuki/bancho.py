using anticheat.Enums;
using Newtonsoft.Json;

namespace anticheat.Models;

internal class Score
{
    [JsonProperty("id")]
    public ulong Id { get; private set; }

    [JsonProperty("bmap")]
    public Beatmap? Beatmap { get; private set; }

    [JsonProperty("player")]
    public Player? Player { get; private set; }

    [JsonProperty("mode")]
    public GameMode Mode { get; private set; }

    [JsonProperty("mods")]
    public int Mods { get; private set; }

    [JsonProperty("pp")]
    public float PP { get; private set; }

    [JsonProperty("sr")]
    public float StarRating { get; private set; }

    [JsonProperty("score")]
    public ulong TotalScore { get; private set; }

    [JsonProperty("max_combo")]
    public int MaxCombo { get; private set; }

    [JsonProperty("acc")]
    public float Accuracy { get; private set; }

    [JsonProperty("n300")]
    public int Count300 { get; private set; }

    [JsonProperty("n100")]
    public int Count100 { get; private set; }

    [JsonProperty("n50")]
    public int Count50 { get; private set; }

    [JsonProperty("nmiss")]
    public int Misses { get; private set; }

    [JsonProperty("ngeki")]
    public int Geki { get; private set; }

    [JsonProperty("nkatu")]
    public int Katu { get; private set; }

    [JsonProperty("grade")]
    public Grade Grade { get; private set; }

    [JsonProperty("passed")]
    public bool Passed { get; private set; }

    [JsonProperty("perfect")]
    public bool Perfect { get; private set; }

    [JsonProperty("status")]
    public SubmissionStatus Status { get; private set; }

    [JsonProperty("client_time")]
    public DateTime ClientTime { get; private set; }

    [JsonProperty("time_elapsed")]
    public int TimeElapsed { get; private set; }

    [JsonProperty("rank")]
    public int Rank { get; private set; }

    public override string ToString()
    {
        return $"<{Beatmap?.Artist} - {Beatmap?.Title} played by {Player?.Name} ({Id})>";
    }
}