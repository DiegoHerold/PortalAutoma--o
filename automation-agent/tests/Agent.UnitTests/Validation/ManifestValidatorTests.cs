using Biason.AutomationAgent.Application.Validation;
using Biason.AutomationAgent.Domain.Contracts;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Validation;

public class ManifestValidatorTests
{
    private readonly IManifestValidator _validator;

    public ManifestValidatorTests()
    {
        var logger = Substitute.For<ILogger<ManifestValidator>>();
        _validator = new ManifestValidator(logger);
    }

    [Fact]
    public async Task ValidManifest_ReturnsValid()
    {
        var json = """
        {
            "schema_version": 1,
            "id": "test.automation",
            "name": "Test Automation",
            "version": "1.0.0",
            "runtime": { "id": "python-core", "version": "3.13" },
            "entrypoint": { "type": "python_function", "module": "main", "callable": "run" },
            "capabilities": { "required": ["windows"] },
            "resources": { "pool": "background", "slots": 1 },
            "timeout": { "execution_seconds": 3600 }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeTrue();
        result.Manifest.Should().NotBeNull();
        result.Manifest!.Id.Should().Be("test.automation");
    }

    [Fact]
    public async Task MissingId_ReturnsInvalid()
    {
        var json = """
        {
            "schema_version": 1,
            "name": "Test",
            "version": "1.0.0",
            "runtime": { "id": "python-core" },
            "entrypoint": { "type": "python_function", "module": "main", "callable": "run" }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("id", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task MissingRuntime_ReturnsInvalid()
    {
        var json = """
        {
            "schema_version": 1,
            "id": "test.automation",
            "name": "Test",
            "version": "1.0.0",
            "entrypoint": { "type": "python_function", "module": "main", "callable": "run" }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("runtime", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task MissingEntrypoint_ReturnsInvalid()
    {
        var json = """
        {
            "schema_version": 1,
            "id": "test.automation",
            "name": "Test",
            "version": "1.0.0",
            "runtime": { "id": "python-core" }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("entrypoint", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task PythonFunctionWithoutModule_ReturnsInvalid()
    {
        var json = """
        {
            "schema_version": 1,
            "id": "test.automation",
            "name": "Test",
            "version": "1.0.0",
            "runtime": { "id": "python-core" },
            "entrypoint": { "type": "python_function", "callable": "run" }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("module", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task InvalidJson_ReturnsInvalid()
    {
        var result = await _validator.ValidateAsync("not json at all");
        result.IsValid.Should().BeFalse();
    }

    [Fact]
    public async Task BrowserManifest_ReturnsValid()
    {
        var json = """
        {
            "schema_version": 1,
            "id": "browser.automation",
            "name": "Browser Test",
            "version": "2.0.0",
            "runtime": { "id": "python-browser", "version": "3.13-playwright" },
            "entrypoint": { "type": "browser_playwright", "module": "automation.main", "callable": "run" },
            "resources": { "pool": "browser", "slots": 1 },
            "timeout": { "execution_seconds": 1800 }
        }
        """;

        var result = await _validator.ValidateContentAsync(json);
        result.IsValid.Should().BeTrue();
    }
}
