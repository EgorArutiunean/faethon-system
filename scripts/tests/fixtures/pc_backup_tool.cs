// Synthetic SSH/Restic process fixture. Never connects to any network service.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

internal static class BackupFixture {
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    private static string Root { get { return Environment.GetEnvironmentVariable("BUY_PULL_FIXTURE_ROOT"); } }
    private static string Scenario { get { return Environment.GetEnvironmentVariable("BUY_PULL_FIXTURE_SCENARIO") ?? ""; } }

    public static int Main(string[] args) {
        try {
            var executable = Path.GetFileNameWithoutExtension(Environment.GetCommandLineArgs()[0]);
            return executable == "ssh" ? Ssh(args) : Restic(args);
        } catch (Exception) {
            Console.Error.WriteLine("Synthetic fixture rejected the invocation.");
            return 71;
        }
    }

    private static void Record(string tool, string[] args) {
        var call = new Dictionary<string, object> {
            { "tool", tool }, { "args", args }, { "cwd", Directory.GetCurrentDirectory() }
        };
        File.AppendAllText(Path.Combine(Root, "calls.jsonl"), Json.Serialize(call) + "\n");
    }

    private static int Ssh(string[] args) {
        Record("ssh", args);
        if (Environment.GetEnvironmentVariables().Keys.Cast<object>()
                .Any(key => key.ToString().StartsWith("RESTIC_", StringComparison.OrdinalIgnoreCase))) return 42;
        var flattened = String.Join("|", args);
        foreach (var flag in new[] { "-F|NUL", "-o|BatchMode=yes", "-o|StrictHostKeyChecking=yes", "-o|IdentitiesOnly=yes", "-i|" }) {
            if (!flattened.Contains(flag)) return 43;
        }
        var target = Array.IndexOf(args, "backup-reader@fixture.invalid");
        if (target < 0) return 44;
        if (Scenario == "ssh-failure") return 23;
        var command = args.Skip(target + 1).ToArray();
        var output = Console.OpenStandardOutput();
        if (command.SequenceEqual(new[] { "list" })) {
            var list = File.ReadAllBytes(Path.Combine(Root, "remote", "list.txt"));
            output.Write(list, 0, list.Length);
            return 0;
        }
        if (command.Length != 2 || command[0] != "get" || !Regex.IsMatch(command[1], @"\Abuy_modern_[0-9]{8}-[0-9]{6}\.dump(?:\.sha256)?\z")) return 45;
        var payload = File.ReadAllBytes(Path.Combine(Root, "remote", command[1]));
        output.Write(payload, 0, payload.Length);
        return Scenario == "get-failure" ? 24 : 0;
    }

    private static int Restic(string[] args) {
        Record("restic", args);
        if (Environment.GetEnvironmentVariable("RESTIC_PASSWORD") != "fixture-only-passphrase") return 46;
        foreach (DictionaryEntry item in Environment.GetEnvironmentVariables()) {
            var key = item.Key.ToString();
            if (key.StartsWith("RESTIC_", StringComparison.OrdinalIgnoreCase) && key != "RESTIC_PASSWORD") return 47;
        }
        if (args.Length < 4 || args[0] != "--repo" || args[2] != "--no-cache") return 48;
        var repository = args[1];
        var command = args[3];
        var stateFile = Path.Combine(repository, "fixture-state.json");
        if (command == "init") {
            if (File.Exists(Path.Combine(repository, "config"))) return 49;
            File.WriteAllText(Path.Combine(repository, "config"), "fixture-repository");
            File.WriteAllText(stateFile, "[]");
            Console.WriteLine("{}");
            return 0;
        }
        if (!File.Exists(Path.Combine(repository, "config"))) return 50;
        if (command == "snapshots") {
            if (Scenario == "snapshots-failure") return 25;
            Console.Write(File.ReadAllText(stateFile));
            return 0;
        }
        if (command == "dump") {
            var restored = Scenario == "corrupt-roundtrip" ? new byte[] { 42 } : File.ReadAllBytes(Path.Combine(Root, "remote", args[5]));
            Console.OpenStandardOutput().Write(restored, 0, restored.Length);
            return 0;
        }
        if (command != "backup") return 51;
        if (Scenario == "backup-failure") return 26;
        var separator = Array.IndexOf(args, "--");
        if (separator < 0 || args.Length != separator + 3) return 52;
        var basename = args[separator + 1];
        if (!Regex.IsMatch(basename, @"\Abuy_modern_[0-9]{8}-[0-9]{6}\.dump\z") || args[separator + 2] != basename + ".sha256") return 53;
        // Assert preservation of arbitrary binary stdout, including NUL bytes.
        if (!File.ReadAllBytes(basename).SequenceEqual(File.ReadAllBytes(Path.Combine(Root, "remote", basename)))) return 54;
        if (!File.Exists(basename + ".sha256")) return 55;
        var tags = new List<string>();
        for (var index = 4; index < separator; index++) {
            if (args[index] == "--tag") tags.Add(args[++index]);
        }
        if (!tags.Contains("buy-modern-staging") || !tags.Contains(basename) || !tags.Contains("source:backup-reader@fixture.invalid")) return 56;
        var snapshots = Json.Deserialize<List<Dictionary<string, object>>>(File.ReadAllText(stateFile));
        snapshots.Add(new Dictionary<string, object> {
            { "id", (snapshots.Count + 1).ToString("x64") }, { "tags", tags },
            { "paths", new[] { basename, basename + ".sha256" } }
        });
        if (Scenario != "missing-snapshot") File.WriteAllText(stateFile, Json.Serialize(snapshots));
        Console.WriteLine("{\"message_type\":\"summary\"}");
        return 0;
    }
}
