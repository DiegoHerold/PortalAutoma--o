namespace Biason.AutomationAgent.Infrastructure.Database;

public sealed record MigrationDefinition(int Version, string Name, string Sql);
