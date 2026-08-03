using System.Text.Json;
using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Serialization;

/// <summary>
/// Opções de serialização compartilhadas por todo o protocolo.
/// Um único ponto de verdade evita divergência entre Agent, Session Runner e simulador.
/// </summary>
public static class ProtocolJson
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower) }
    };

    public static string Serialize<T>(T value) => JsonSerializer.Serialize(value, Options);

    public static T? Deserialize<T>(string json) => JsonSerializer.Deserialize<T>(json, Options);

    /// <summary>
    /// Reinterpreta um <c>payload</c> genérico (JsonElement ou objeto) como tipo concreto.
    /// Retorna null quando o payload não corresponde ao formato esperado.
    /// </summary>
    public static T? ReadPayload<T>(object? payload) where T : class
    {
        switch (payload)
        {
            case null:
                return null;
            case T typed:
                return typed;
            case JsonElement element:
                try { return element.Deserialize<T>(Options); }
                catch (JsonException) { return null; }
            default:
                try { return JsonSerializer.Deserialize<T>(JsonSerializer.Serialize(payload, Options), Options); }
                catch (JsonException) { return null; }
        }
    }
}
