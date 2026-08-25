// Biason - Demo Executavel: Validacao de Contratos
//
// Executavel real de demonstracao: le uma lista de contratos (via
// input.json, se o Portal enviar parametros), "valida" cada um com um
// pequeno delay para simular trabalho real, reporta progresso via stdout
// e escreve um relatorio como artefato - exatamente o mesmo caminho que
// uma automacao do tipo "executable" real percorreria no Agent (o .exe
// empacotado dentro do pacote da automacao, sem depender de nenhum
// runtime baixado).

using System.Text.Json;

var workspace = Environment.GetEnvironmentVariable("AUTOMATION_WORKSPACE") ?? Directory.GetCurrentDirectory();
var artifactsPath = Environment.GetEnvironmentVariable("AUTOMATION_ARTIFACTS_PATH")
    ?? Path.Combine(workspace, "artifacts");
Directory.CreateDirectory(artifactsPath);

var contratos = new List<string>
{
    "contrato_cliente_001.pdf",
    "contrato_cliente_002.pdf",
    "contrato_cliente_003.pdf",
    "termo_confidencialidade_2026.pdf",
};

var inputPath = Path.Combine(workspace, "input", "input.json");
if (File.Exists(inputPath))
{
    try
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(inputPath));
        if (doc.RootElement.TryGetProperty("contratos", out var arr) && arr.ValueKind == JsonValueKind.Array)
        {
            var fromInput = arr.EnumerateArray()
                .Select(e => e.GetString() ?? string.Empty)
                .Where(s => s.Length > 0)
                .ToList();
            if (fromInput.Count > 0) contratos = fromInput;
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[Biason] Aviso: nao consegui ler input.json ({ex.Message}), usando lista padrao.");
    }
}

Console.WriteLine($"[Biason] Iniciando validacao de {contratos.Count} contrato(s)...");

var resultados = new List<(string Documento, string ValidadoEm)>();
for (var i = 0; i < contratos.Count; i++)
{
    var documento = contratos[i];
    Console.WriteLine($"[Biason] Validando {i + 1}/{contratos.Count}: {documento}");
    Thread.Sleep(1000);
    resultados.Add((documento, DateTime.UtcNow.ToString("o")));
    var pct = (i + 1) * 100 / contratos.Count;
    Console.WriteLine($"[Biason] Progresso: {i + 1}/{contratos.Count} ({pct}%)");
}

var reportPath = Path.Combine(artifactsPath, "relatorio_validacao_contratos.txt");
using (var writer = new StreamWriter(reportPath, false, System.Text.Encoding.UTF8))
{
    writer.WriteLine("Biason Assessoria Empresarial");
    writer.WriteLine("Relatorio de Validacao de Contratos (demo)");
    writer.WriteLine("=============================================");
    writer.WriteLine();
    writer.WriteLine($"Executado em: {DateTime.UtcNow:o}");
    writer.WriteLine($"Total de contratos: {contratos.Count}");
    writer.WriteLine();
    foreach (var (documento, validadoEm) in resultados)
    {
        writer.WriteLine($"  - {documento}: validado ({validadoEm})");
    }
}

Console.WriteLine($"[Biason] Relatorio gravado em {reportPath}");
Console.WriteLine("[Biason] Validacao concluida com sucesso.");

return 0;
