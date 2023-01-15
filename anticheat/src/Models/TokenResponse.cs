using Newtonsoft.Json;

namespace anticheat.Models;

internal class TokenResponse
{
    [JsonProperty("access_token")]
    public string AccessToken { get; private set; } = "";

    [JsonProperty("refresh_token")]
    public string RefreshToken { get; private set; } = "";

    [JsonProperty("expire_date")]
    public DateTime ExpireDate { get; private set; }
}
