using Biason.AutomationAgent.Application.Connection;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Connection;

public class ConnectionBackoffCalculatorTests
{
    /// <summary>Fonte de jitter fixa — sempre devolve o mesmo valor, para testes determinísticos.</summary>
    private sealed class FixedJitterSource : IJitterSource
    {
        private readonly double _value;
        public FixedJitterSource(double value) => _value = value;
        public double NextDouble() => _value;
    }

    [Fact]
    public void NextDelay_WithFullJitter_NeverExceedsExponentialCap()
    {
        var calculator = new ConnectionBackoffCalculator(
            TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(60), new FixedJitterSource(1.0));

        // jitter = 1.0 => full jitter no volta ao valor exponencial cheio (ainda respeitando o teto).
        calculator.NextDelay(1).TotalMilliseconds.Should().BeApproximately(1000, 1);
        calculator.NextDelay(2).TotalMilliseconds.Should().BeApproximately(2000, 1);
        calculator.NextDelay(3).TotalMilliseconds.Should().BeApproximately(4000, 1);
        calculator.NextDelay(4).TotalMilliseconds.Should().BeApproximately(8000, 1);
    }

    [Fact]
    public void NextDelay_NeverExceedsConfiguredMaximum()
    {
        var calculator = new ConnectionBackoffCalculator(
            TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(10), new FixedJitterSource(1.0));

        // Tentativa alta o bastante para que o exponencial estoure o teto de 10s.
        calculator.NextDelay(10).TotalSeconds.Should().BeLessThanOrEqualTo(10);
    }

    [Fact]
    public void NextDelay_WithZeroJitter_ReturnsMinimumFloor()
    {
        var calculator = new ConnectionBackoffCalculator(
            TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(60), new FixedJitterSource(0.0));

        // jitter = 0 daria 0ms — o piso de 100ms evita virar busy-loop.
        calculator.NextDelay(1).TotalMilliseconds.Should().Be(100);
    }

    [Fact]
    public void NextDelay_AttemptLessThanOne_TreatedAsFirstAttempt()
    {
        var calculator = new ConnectionBackoffCalculator(
            TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(60), new FixedJitterSource(1.0));

        calculator.NextDelay(0).Should().Be(calculator.NextDelay(1));
        calculator.NextDelay(-5).Should().Be(calculator.NextDelay(1));
    }

    [Fact]
    public void NextDelay_DifferentAttempts_ProduceIncreasingCeilings()
    {
        // Com jitter aleatório real, o valor exato varia — mas repetindo muitas vezes o
        // máximo observado por tentativa deve crescer, confirmando o crescimento exponencial.
        var calculator = new ConnectionBackoffCalculator(TimeSpan.FromMilliseconds(50), TimeSpan.FromSeconds(30));

        double MaxOverManySamples(int attempt)
        {
            double max = 0;
            for (var i = 0; i < 200; i++)
                max = Math.Max(max, calculator.NextDelay(attempt).TotalMilliseconds);
            return max;
        }

        MaxOverManySamples(1).Should().BeLessThan(MaxOverManySamples(5));
    }

    [Fact]
    public void Constructor_RejectsNonPositiveInitial()
    {
        var act = () => new ConnectionBackoffCalculator(TimeSpan.Zero, TimeSpan.FromSeconds(10));
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    [Fact]
    public void Constructor_RejectsMaximumBelowInitial()
    {
        var act = () => new ConnectionBackoffCalculator(TimeSpan.FromSeconds(10), TimeSpan.FromSeconds(5));
        act.Should().Throw<ArgumentOutOfRangeException>();
    }
}
