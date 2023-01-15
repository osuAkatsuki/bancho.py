using Newtonsoft.Json;

namespace anticheat.Models;

internal class Config
{
    [JsonProperty("domain")]
    public string Domain { get; private set; } = "cmyui.xyz";

    [JsonProperty("rabbitmq_hostname")]
    public string RabbitMQHostname { get; private set; } = "localhost";

    [JsonProperty("rabbitmq_port")]
    public ushort RabbitMQPort { get; private set; } = 5672;

    [JsonProperty("debug")]
    public bool Debug { get; private set; } = false;

    [JsonProperty("include_anticheat_identifier_in_restriction_reason")]
    public bool IncludeAnticheatIdentifier { get; private set; } = true;

    public void Save(string filename)
    {
        File.WriteAllText(filename, JsonConvert.SerializeObject(this, Formatting.Indented));
    }

    public static Config? Load(string filename)
    {
        return JsonConvert.DeserializeObject<Config>(File.ReadAllText(filename));
    }
}
