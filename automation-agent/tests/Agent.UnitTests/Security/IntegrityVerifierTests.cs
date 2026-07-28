using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Infrastructure.Security;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Security;

public class IntegrityVerifierTests
{
    private readonly IntegrityVerifier _sut;
    private readonly string _tempDir;

    public IntegrityVerifierTests()
    {
        var options = Options.Create(new DownloadOptions
        {
            MaxCompressionRatio = 100,
            MaxExtractedSizeMb = 2048
        });
        var secOptions = Options.Create(new SecurityOptions
        {
            RequireHashVerification = true,
            BlockPathTraversal = true
        });
        var logger = Substitute.For<ILogger<IntegrityVerifier>>();
        _sut = new IntegrityVerifier(options, secOptions, logger);
        _tempDir = Path.Combine(Path.GetTempPath(), $"integrity_test_{Guid.NewGuid():N}");
        Directory.CreateDirectory(_tempDir);
    }

    [Fact]
    public async Task ComputeSha256_ReturnsCorrectHash()
    {
        var filePath = Path.Combine(_tempDir, "test.txt");
        await File.WriteAllTextAsync(filePath, "hello world");

        var hash = await _sut.ComputeSha256Async(filePath);

        hash.Should().NotBeNullOrEmpty();
        hash.Should().HaveLength(64); // SHA-256 hex = 64 chars
    }

    [Fact]
    public async Task VerifySha256_MatchingHash_ReturnsTrue()
    {
        var filePath = Path.Combine(_tempDir, "test2.txt");
        await File.WriteAllTextAsync(filePath, "test content");

        var hash = await _sut.ComputeSha256Async(filePath);
        var valid = await _sut.VerifySha256Async(filePath, hash);

        valid.Should().BeTrue();
    }

    [Fact]
    public async Task VerifySha256_WrongHash_ReturnsFalse()
    {
        var filePath = Path.Combine(_tempDir, "test3.txt");
        await File.WriteAllTextAsync(filePath, "test content");

        var valid = await _sut.VerifySha256Async(filePath, "0000000000000000000000000000000000000000000000000000000000000000");

        valid.Should().BeFalse();
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }
}
