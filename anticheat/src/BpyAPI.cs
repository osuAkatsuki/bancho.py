using System.Net.Http.Headers;
using anticheat.Models;
using Newtonsoft.Json;

namespace anticheat;

internal class BpyAPI
{
    Dictionary<string, string> _authorizationBody = new Dictionary<string, string>()
    {
        { "client_id", "" },
        { "client_secret", "" },
        { "grant_type", "credentials" },
        { "scope", "admin" }
    };

    private string _apiUrl = "";

    private DateTime _expireDate = DateTime.MinValue;

    private HttpClient _httpClient = new HttpClient();

    public BpyAPI(string domain, string clientId, string clientSecret)
    {
        _apiUrl = $"https://api.{domain}";
        _authorizationBody["client_id"] = clientId;
        _authorizationBody["client_secret"] = clientSecret;
    }

    private async void EnsureValidAccessToken()
    {
        // Check if the access token expired
        if (DateTime.Now.AddSeconds(10) < _expireDate /* buffer */)
            return;

        // Perform the authorization and deserialize the response
        HttpContent body = new FormUrlEncodedContent(_authorizationBody);
        HttpResponseMessage response = await _httpClient.PostAsync($"{_apiUrl}/token", body);
        TokenResponse? tokenResponse = JsonConvert.DeserializeObject<TokenResponse>(await response.Content.ReadAsStringAsync());
        if (tokenResponse == null)
            throw new NullReferenceException("The deserialized authorization response is null.");

        // If it's the first authorization make sure to set the grant type to refresh token from here on
        if (!_authorizationBody.ContainsKey("refresh_token"))
            _authorizationBody["grant_type"] = "refresh_token";

        // Apply the received access token and remember the refresh token for the next authorization
        _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", tokenResponse.AccessToken);
        _authorizationBody["refresh_token"] = tokenResponse.RefreshToken;
        _expireDate = tokenResponse.ExpireDate;
    }
}
