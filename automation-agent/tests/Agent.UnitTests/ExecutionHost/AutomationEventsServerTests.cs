using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Biason.AutomationAgent.ExecutionHost.Protocol;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.ExecutionHost;

[SupportedOSPlatform("windows")]
public sealed class AutomationEventsServerTests : IAsyncDisposable
{
    private readonly List<JsonElement> _forwarded = [];
    private readonly AutomationEventsServer _server;

    public AutomationEventsServerTests()
    {
        _server = AutomationEventsServer.Create("att_teste_1", (evento, _) =>
        {
            lock (_forwarded)
                _forwarded.Add(evento);
            return Task.CompletedTask;
        });
        _server.Start();
    }

    [Fact]
    public async Task TokenErrado_RecebeErroENaoRepassaNada()
    {
        await using var client = await ConnectAsync();
        await client.SendAsync(new JsonObject { ["tipo"] = "ola", ["token"] = "token-de-outra-execucao" });

        var resposta = await client.ReadAsync();

        resposta!["tipo"]!.GetValue<string>().Should().Be("erro");
        resposta["motivo"]!.GetValue<string>().Should().Be("token_invalido");
        _forwarded.Should().BeEmpty();
    }

    [Fact]
    public async Task EventoValido_RepassaIntactoERecebeAck()
    {
        await using var client = await ConnectAuthenticatedAsync();
        var evento = Evento(1, "log", new JsonObject { ["nivel"] = "info", ["texto"] = "Abrindo a Domínio" });

        await client.SendAsync(new JsonObject { ["tipo"] = "evento", ["evento"] = evento });
        var ack = await client.ReadAsync();

        ack!["tipo"]!.GetValue<string>().Should().Be("ack");
        ack["sequencia"]!.GetValue<long>().Should().Be(1);
        _forwarded.Should().ContainSingle();
        JsonNode.Parse(_forwarded[0].GetRawText())!.ToJsonString().Should().Be(evento.ToJsonString());
    }

    [Fact]
    public async Task ReenvioDaMesmaSequencia_RecebeAckSemDuplicar()
    {
        await using var client = await ConnectAuthenticatedAsync();
        var mensagem = new JsonObject { ["tipo"] = "evento", ["evento"] = Evento(1, "progresso", new JsonObject { ["atual"] = 1, ["total"] = 50 }) };

        await client.SendAsync(mensagem);
        (await client.ReadAsync())!["tipo"]!.GetValue<string>().Should().Be("ack");
        await client.SendAsync(JsonNode.Parse(mensagem.ToJsonString())!.AsObject());
        (await client.ReadAsync())!["tipo"]!.GetValue<string>().Should().Be("ack");

        _forwarded.Should().ContainSingle();
        _server.HighestSequence.Should().Be(1);
    }

    [Fact]
    public async Task ReconexaoDepoisDeCair_ContinuaDaUltimaSequencia()
    {
        await using (var primeira = await ConnectAuthenticatedAsync())
        {
            await primeira.SendAsync(new JsonObject { ["tipo"] = "evento", ["evento"] = Evento(1, "log", Log("um")) });
            await primeira.ReadAsync();
        }

        await using var segunda = await ConnectAsync();
        await segunda.SendAsync(new JsonObject { ["tipo"] = "ola", ["token"] = _server.Token });
        var ok = await segunda.ReadAsync();
        ok!["ultima_sequencia"]!.GetValue<long>().Should().Be(1);

        await segunda.SendAsync(new JsonObject { ["tipo"] = "evento", ["evento"] = Evento(2, "log", Log("dois")) });
        (await segunda.ReadAsync())!["sequencia"]!.GetValue<long>().Should().Be(2);
        _forwarded.Should().HaveCount(2);
    }

    [Fact]
    public async Task VersaoDiferente_RecebeErroENaoRepassa()
    {
        await using var client = await ConnectAuthenticatedAsync();
        var evento = Evento(1, "log", Log("x"));
        evento["protocol_version"] = "automation-events/9";

        await client.SendAsync(new JsonObject { ["tipo"] = "evento", ["evento"] = evento });

        (await client.ReadAsync())!["motivo"]!.GetValue<string>().Should().Be("versao_incompativel");
        _forwarded.Should().BeEmpty();
    }

    [Fact]
    public async Task LinhaAcimaDoLimite_EncerraAConexaoSemRepassar()
    {
        await using var client = await ConnectAuthenticatedAsync();
        await client.SendRawAsync(new string('x', AutomationEventsServer.MaxLineChars + 10));

        (await client.ReadAsync())!["motivo"]!.GetValue<string>().Should().Be("mensagem_grande_demais");
        _forwarded.Should().BeEmpty();
    }

    [Fact]
    public async Task ComandoSemAutomacaoConectada_EntregueQuandoElaConecta()
    {
        await _server.SendCommandAsync("cancelar", "tempo limite");

        await using var client = await ConnectAsync();
        await client.SendAsync(new JsonObject { ["tipo"] = "ola", ["token"] = _server.Token });
        (await client.ReadAsync())!["tipo"]!.GetValue<string>().Should().Be("ok");
        var comando = await client.ReadAsync();

        comando!["tipo"]!.GetValue<string>().Should().Be("comando");
        comando["comando"]!["type"]!.GetValue<string>().Should().Be("cancelar");
        comando["comando"]!["protocol_version"]!.GetValue<string>().Should().Be("automation-events/1");
    }

    [Fact]
    public async Task Ping_RecebeComandoPendenteAntesDoPong()
    {
        await using var client = await ConnectAuthenticatedAsync();
        await _server.SendCommandAsync("parar_apos_item");
        await client.SendAsync(new JsonObject { ["tipo"] = "ping" });

        (await client.ReadAsync())!["comando"]!["type"]!.GetValue<string>().Should().Be("parar_apos_item");
        (await client.ReadAsync())!["tipo"]!.GetValue<string>().Should().Be("pong");
    }

    // Regressao: com o pipe sem buffer, o comando "cancelar" do encerramento por tempo
    // limite esperava a automacao ler e o ExecutionHost nunca encerrava o processo.
    [Fact]
    public async Task Comando_ComAutomacaoQueNaoLeOPipe_NaoTravaQuemEnvia()
    {
        await using var client = await ConnectAuthenticatedAsync();

        var envio = _server.SendCommandAsync("cancelar", "tempo limite");
        var terminou = await Task.WhenAny(envio, Task.Delay(TimeSpan.FromSeconds(10)));

        terminou.Should().BeSameAs(envio, "o envio do comando nao pode depender da automacao ler o pipe");
        await envio;
    }

    private static JsonObject Log(string texto) => new() { ["nivel"] = "info", ["texto"] = texto };

    private static JsonObject Evento(long sequence, string type, JsonObject payload) => new()
    {
        ["protocol_version"] = "automation-events/1",
        ["event_id"] = Guid.NewGuid().ToString(),
        ["sequence"] = sequence,
        ["type"] = type,
        ["occurred_at"] = "2026-11-09T14:03:21.512Z",
        ["payload"] = payload,
    };

    private async Task<Client> ConnectAuthenticatedAsync()
    {
        var client = await ConnectAsync();
        await client.SendAsync(new JsonObject { ["tipo"] = "ola", ["token"] = _server.Token });
        var ok = await client.ReadAsync();
        ok!["tipo"]!.GetValue<string>().Should().Be("ok");
        return client;
    }

    private async Task<Client> ConnectAsync()
    {
        var pipe = new NamedPipeClientStream(".", _server.PipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        await pipe.ConnectAsync(5000);
        return new Client(pipe);
    }

    public async ValueTask DisposeAsync() => await _server.DisposeAsync();

    private sealed class Client(NamedPipeClientStream pipe) : IAsyncDisposable
    {
        private readonly StreamReader _reader = new(pipe, new UTF8Encoding(false), false, 1024, leaveOpen: true);
        private readonly StreamWriter _writer = new(pipe, new UTF8Encoding(false), 1024, leaveOpen: true) { AutoFlush = true };

        public Task SendAsync(JsonObject message) => SendRawAsync(message.ToJsonString());

        public async Task SendRawAsync(string line)
        {
            try { await _writer.WriteLineAsync(line); }
            catch (IOException) { /* o servidor pode fechar antes de ler tudo */ }
        }

        public async Task<JsonObject?> ReadAsync()
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            var line = await _reader.ReadLineAsync(timeout.Token);
            return line is null ? null : JsonNode.Parse(line)!.AsObject();
        }

        public async ValueTask DisposeAsync()
        {
            _reader.Dispose();
            try { await _writer.DisposeAsync(); } catch (IOException) { }
            await pipe.DisposeAsync();
        }
    }
}
