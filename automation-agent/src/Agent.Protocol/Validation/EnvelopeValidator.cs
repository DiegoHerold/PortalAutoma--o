using System.Text;
using System.Text.Json;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;

namespace Biason.AutomationAgent.Protocol.Validation;

/// <summary>
/// Porta de entrada de toda mensagem recebida do Portal.
/// Nenhuma mensagem chega ao Command Dispatcher sem passar por aqui (seção 8).
/// </summary>
public static class EnvelopeValidator
{
    /// <summary>
    /// Analisa o texto bruto vindo do socket e valida o envelope.
    /// Retorna o envelope apenas quando o resultado for válido.
    /// </summary>
    public static (EnvelopeValidationResult Result, ProtocolEnvelope? Envelope) ParseInbound(
        string rawJson,
        DateTime nowUtc,
        string? expectedAgentId = null,
        int maxSizeBytes = ProtocolConstants.MaxMessageSizeBytes)
    {
        if (string.IsNullOrWhiteSpace(rawJson))
            return (EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MalformedJson, "Mensagem vazia."), null);

        var byteCount = Encoding.UTF8.GetByteCount(rawJson);
        if (byteCount > maxSizeBytes)
        {
            return (EnvelopeValidationResult.Invalid(
                ProtocolErrorCodes.PayloadTooLarge,
                $"Mensagem de {byteCount} bytes excede o limite de {maxSizeBytes} bytes."), null);
        }

        ProtocolEnvelope? envelope;
        try
        {
            envelope = ProtocolJson.Deserialize<ProtocolEnvelope>(rawJson);
        }
        catch (JsonException ex)
        {
            return (EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MalformedJson, ex.Message), null);
        }

        if (envelope is null)
            return (EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MalformedJson, "Envelope nulo."), null);

        var result = ValidateInbound(envelope, nowUtc, expectedAgentId);
        return (result, result.IsValid ? envelope : null);
    }

    public static EnvelopeValidationResult ValidateInbound(
        ProtocolEnvelope envelope,
        DateTime nowUtc,
        string? expectedAgentId = null)
    {
        if (string.IsNullOrWhiteSpace(envelope.ProtocolVersion))
            return EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MissingProtocolVersion, "protocol_version ausente.");

        if (!IsVersionCompatible(envelope.ProtocolVersion, out var versionError))
            return EnvelopeValidationResult.Invalid(ProtocolErrorCodes.UnsupportedProtocolVersion, versionError!);

        if (string.IsNullOrWhiteSpace(envelope.MessageId))
            return EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MissingMessageId, "message_id ausente.");

        if (string.IsNullOrWhiteSpace(envelope.MessageType))
            return EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MissingMessageType, "message_type ausente.");

        if (!PortalMessageTypes.IsKnown(envelope.MessageType))
        {
            return EnvelopeValidationResult.Invalid(
                ProtocolErrorCodes.UnknownMessageType,
                $"Tipo de mensagem desconhecido: {envelope.MessageType}");
        }

        if (!PortalMessageTypes.Inbound.Contains(envelope.MessageType))
        {
            return EnvelopeValidationResult.Invalid(
                ProtocolErrorCodes.UnexpectedDirection,
                $"O Portal não pode enviar '{envelope.MessageType}' ao Agent.");
        }

        if (envelope.SentAt == default)
            return EnvelopeValidationResult.Invalid(ProtocolErrorCodes.MissingSentAt, "sent_at ausente.");

        var skew = (envelope.SentAt - nowUtc).Duration();
        if (skew > ProtocolConstants.MaxClockSkew)
        {
            return EnvelopeValidationResult.Invalid(
                ProtocolErrorCodes.ClockSkewTooLarge,
                $"sent_at diverge do relógio local em {skew.TotalMinutes:F1} minutos.");
        }

        // Uma vez registrado, o Agent só aceita mensagens endereçadas a ele.
        if (!string.IsNullOrWhiteSpace(expectedAgentId) &&
            !string.IsNullOrWhiteSpace(envelope.AgentId) &&
            !string.Equals(envelope.AgentId, expectedAgentId, StringComparison.Ordinal))
        {
            return EnvelopeValidationResult.Invalid(
                ProtocolErrorCodes.AgentMismatch,
                "Mensagem endereçada a outro agent_id.");
        }

        return EnvelopeValidationResult.Valid;
    }

    /// <summary>
    /// Compatibilidade por major version: 1.x é aceito por um Agent 1.0,
    /// 2.x é rejeitado explicitamente.
    /// </summary>
    public static bool IsVersionCompatible(string version, out string? error)
    {
        error = null;
        var majorPart = version.Split('.')[0];

        if (!int.TryParse(majorPart, out var major))
        {
            error = $"protocol_version inválido: '{version}'.";
            return false;
        }

        if (major != ProtocolConstants.SupportedMajorVersion)
        {
            error = $"protocol_version {version} incompatível; suportado: {ProtocolConstants.SupportedMajorVersion}.x";
            return false;
        }

        return true;
    }

    /// <summary>Garante que o Agent não emita mensagem acima do limite do socket.</summary>
    public static bool TrySerializeOutbound(ProtocolEnvelope envelope, out string json, out string? error)
    {
        json = ProtocolJson.Serialize(envelope);
        var size = Encoding.UTF8.GetByteCount(json);

        if (size > ProtocolConstants.MaxMessageSizeBytes)
        {
            error = $"Mensagem {envelope.MessageType} tem {size} bytes e excede o limite de " +
                    $"{ProtocolConstants.MaxMessageSizeBytes} bytes. Use upload HTTPS para conteúdo grande.";
            return false;
        }

        error = null;
        return true;
    }
}
