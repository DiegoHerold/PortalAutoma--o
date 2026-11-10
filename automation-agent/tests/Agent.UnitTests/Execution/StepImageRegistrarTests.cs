using System.Text.Json;
using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.UnitTests.Execution;

public class StepImageRegistrarTests : IDisposable
{
    private readonly IArtifactManager _artifacts = Substitute.For<IArtifactManager>();
    private readonly StepImageRegistrar _sut;
    private readonly string _workspace = Path.Combine(Path.GetTempPath(), $"passos_{Guid.NewGuid():N}");
    private readonly ExecutionContext _context;

    public StepImageRegistrarTests()
    {
        _sut = new StepImageRegistrar(_artifacts, Substitute.For<ILogger<StepImageRegistrar>>());
        Directory.CreateDirectory(Path.Combine(_workspace, "artifacts", "passos"));
        _context = new ExecutionContext { ExecutionId = "exe_1", AttemptId = "att_1", WorkspacePath = _workspace };
    }

    private static JsonElement Passo(string? imagemId, string tipo = "passo")
    {
        var payload = imagemId is null ? "{\"rotulo\":\"x\",\"tipo\":\"acao\"}" : $"{{\"rotulo\":\"x\",\"tipo\":\"acao\",\"imagem_id\":\"{imagemId}\"}}";
        return JsonDocument.Parse($"{{\"type\":\"{tipo}\",\"sequence\":3,\"payload\":{payload}}}").RootElement.Clone();
    }

    private void Imagem(string id) => File.WriteAllBytes(Path.Combine(_workspace, "artifacts", "passos", id + ".jpg"), new byte[] { 0xFF, 0xD8, 0xFF, 1, 2, 3 });

    [Fact]
    public async Task Passo_com_imagem_registra_o_arquivo_para_subir_ja()
    {
        Imagem("img_abc");

        var registrou = await _sut.TryRegisterAsync(_context, Passo("img_abc"));

        registrou.Should().BeTrue();
        await _artifacts.Received(1).RegisterAsync("exe_1", "att_1", Arg.Is<IReadOnlyList<ExecutionArtifactRef>>(lista =>
            lista.Count == 1 &&
            lista[0].Name == "passos/img_abc.jpg" &&
            lista[0].ContentType == "image/jpeg" &&
            lista[0].SizeBytes == 6 &&
            lista[0].LocalPath == Path.Combine(_workspace, "artifacts", "passos", "img_abc.jpg") &&
            lista[0].ArtifactId == StepImageRegistrar.ArtifactIdFor("att_1", "img_abc")), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Mesmo_passo_duas_vezes_registra_uma_so()
    {
        Imagem("img_rep");

        (await _sut.TryRegisterAsync(_context, Passo("img_rep"))).Should().BeTrue();
        (await _sut.TryRegisterAsync(_context, Passo("img_rep"))).Should().BeFalse();

        await _artifacts.Received(1).RegisterAsync(Arg.Any<string>(), Arg.Any<string>(), Arg.Any<IReadOnlyList<ExecutionArtifactRef>>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public void Id_do_artefato_e_o_mesmo_depois_de_reiniciar()
    {
        StepImageRegistrar.ArtifactIdFor("att_1", "img_a").Should().Be(StepImageRegistrar.ArtifactIdFor("att_1", "img_a"));
        StepImageRegistrar.ArtifactIdFor("att_1", "img_a").Should().NotBe(StepImageRegistrar.ArtifactIdFor("att_2", "img_a"));
        StepImageRegistrar.ArtifactIdFor("att_1", "img_a").Should().MatchRegex("^art_[0-9a-f]{32}$");
    }

    [Theory]
    [InlineData(null, "passo")]
    [InlineData("img_a", "log")]
    [InlineData("../../segredos", "passo")]
    [InlineData("img a", "passo")]
    public async Task Nao_registra_o_que_nao_e_imagem_de_passo_valida(string? imagemId, string tipo)
    {
        Imagem("img_a");

        (await _sut.TryRegisterAsync(_context, Passo(imagemId, tipo))).Should().BeFalse();

        await _artifacts.DidNotReceiveWithAnyArgs().RegisterAsync(default!, default!, default!, default);
    }

    [Fact]
    public async Task Passo_sem_o_arquivo_nao_registra_e_tenta_de_novo_depois()
    {
        (await _sut.TryRegisterAsync(_context, Passo("img_tarde"))).Should().BeFalse();
        Imagem("img_tarde");
        (await _sut.TryRegisterAsync(_context, Passo("img_tarde"))).Should().BeTrue();
    }

    public void Dispose()
    {
        if (Directory.Exists(_workspace)) Directory.Delete(_workspace, recursive: true);
    }
}
