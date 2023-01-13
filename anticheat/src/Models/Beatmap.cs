using anticheat.Enums;
using Newtonsoft.Json;

namespace anticheat.Models;

internal class Beatmap
{
        [JsonProperty("md5")]
        public string? Md5 { get; set; }

        [JsonProperty("id")]
        public ulong Id { get; set; }

        [JsonProperty("set_id")]
        public ulong SetId { get; set; }

        [JsonProperty("artist")]
        public string? Artist { get; set; }

        [JsonProperty("title")]
        public string? Title { get; set; }

        [JsonProperty("version")]
        public string?Version { get; set; }

        [JsonProperty("creator")]
        public string? Creator { get; set; }

        [JsonProperty("last_update")]
        public DateTime LastUpdate { get; set; }

        [JsonProperty("total_length")]
        public int TotalLength { get; set; }

        [JsonProperty("max_combo")]
        public int MaxCombo { get; set; }

        [JsonProperty("status")]
        public MapStatus Status { get; set; }

        [JsonProperty("frozen")]
        public bool Frozen { get; set; }

        [JsonProperty("plays")]
        public int Plays { get; set; }

        [JsonProperty("passes")]
        public int Passes { get; set; }

        [JsonProperty("mode")]
        public GameMode Mode { get; set; }

        [JsonProperty("bpm")]
        public double BPM { get; set; }

        [JsonProperty("cs")]
        public double CS { get; set; }

        [JsonProperty("od")]
        public double OD { get; set; }

        [JsonProperty("ar")]
        public double AR { get; set; }

        [JsonProperty("hp")]
        public double HP { get; set; }

        [JsonProperty("diff")]
        public double StarRating { get; set; }

        [JsonProperty("filename")]
        public string? Filename { get; set; }
}