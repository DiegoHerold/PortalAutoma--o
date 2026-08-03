namespace Biason.AutomationAgent.Application.Connection;

/// <summary>Fonte de aleatoriedade injetável — permite jitter determinístico em teste.</summary>
public interface IJitterSource
{
    /// <summary>Número em [0, 1).</summary>
    double NextDouble();
}

public sealed class RandomJitterSource : IJitterSource
{
    public double NextDouble() => Random.Shared.NextDouble();
}

/// <summary>
/// Backoff exponencial com "full jitter" (seção 11): em vez de sempre esperar o valor
/// exponencial cheio, sorteia um valor entre 0 e o teto exponencial. Isso evita que
/// muitos Agents reconectando ao mesmo tempo (ex.: Portal reiniciou) batam no Portal
/// no mesmo instante.
/// </summary>
public sealed class ConnectionBackoffCalculator
{
    private readonly TimeSpan _initial;
    private readonly TimeSpan _maximum;
    private readonly IJitterSource _jitter;

    public ConnectionBackoffCalculator(TimeSpan initial, TimeSpan maximum, IJitterSource? jitter = null)
    {
        if (initial <= TimeSpan.Zero)
            throw new ArgumentOutOfRangeException(nameof(initial), "O backoff inicial deve ser positivo.");
        if (maximum < initial)
            throw new ArgumentOutOfRangeException(nameof(maximum), "O backoff máximo não pode ser menor que o inicial.");

        _initial = initial;
        _maximum = maximum;
        _jitter = jitter ?? new RandomJitterSource();
    }

    /// <param name="attempt">Tentativa 1-based (primeira reconexão = 1).</param>
    public TimeSpan NextDelay(int attempt)
    {
        if (attempt < 1) attempt = 1;

        // Cap exponencial: initial * 2^(attempt-1), sem estourar TimeSpan nem passar de _maximum.
        var exponent = Math.Min(attempt - 1, 30); // evita overflow de double em attempts absurdos
        var uncappedMs = _initial.TotalMilliseconds * Math.Pow(2, exponent);
        var capMs = Math.Min(uncappedMs, _maximum.TotalMilliseconds);

        var jitteredMs = capMs * _jitter.NextDouble();

        // Nunca menor que um piso mínimo perceptível, para não virar busy-loop.
        var flooredMs = Math.Max(jitteredMs, 100);

        return TimeSpan.FromMilliseconds(flooredMs);
    }
}
