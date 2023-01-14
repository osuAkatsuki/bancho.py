using anticheat.Enums;
using anticheat.Models;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace anticheat.Converters;

internal class PlayerStatsConverter : JsonConverter<Dictionary<GameMode, ModeData>>
{
    public override Dictionary<GameMode, ModeData>? ReadJson(JsonReader reader, Type objectType, Dictionary<GameMode, ModeData>? existingValue, bool hasExistingValue, JsonSerializer serializer)
    {
        Dictionary<string, ModeData> stats = JsonConvert.DeserializeObject<Dictionary<string, ModeData>>(JObject.Load(reader).ToString())!;

        return stats.ToDictionary(kvp => Enum.Parse<GameMode>(kvp.Key.Replace("!", "_").ToUpper()), kvp => kvp.Value);
    }

    public override void WriteJson(JsonWriter writer, Dictionary<GameMode, ModeData>? value, JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}