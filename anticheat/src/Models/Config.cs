using Newtonsoft.Json;

namespace anticheat.Models;

internal class Config
{
    [JsonProperty("rabbitmq_hostname")]
    public string RabbitMQHostname { get; private set; } = "localhost";

    [JsonProperty("rabbitmq_port")]
    public ushort RabbitMQPort { get; private set; } = 5672;

    public void Save(string filename)
    {
        File.WriteAllText(filename, JsonConvert.SerializeObject(this, Formatting.Indented));
    }

    public static Config? Load(string filename)
    {
        return JsonConvert.DeserializeObject<Config>(File.ReadAllText(filename));
    }
}