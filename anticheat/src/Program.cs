using Newtonsoft.Json;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using System;
using System.Text;
using anticheat.Models;
using System.Reflection;
using anticheat.Checks;

namespace anticheat;

internal class Program
{
    private static Config _config = new Config();

    public static void Main()
    {
        _config = new Config();

        if (!File.Exists("config.json"))
        {
            _config.Save("config.json");
            Log("Default config.json created. Set up the config file and re-run the service.", ConsoleColor.Magenta);
            return;
        }

        try
        {
            _config = Config.Load("config.json") ?? new Config();
            Log("Config loaded.", ConsoleColor.Magenta);
        }
        catch (Exception ex)
        {
            Log("An error occured while parsing the config file:", ConsoleColor.Red);
            Log(ex.Message, ConsoleColor.Red);
        }

        // Save the config file again to get rid of all old config settings
        _config.Save("config.json");


        ScoreQueue queue = new ScoreQueue(_config.RabbitMQHostname, _config.RabbitMQPort);

        try
        {
            queue.Connect();
        }
        catch (Exception ex)
        {
            Log("An error occured while setting up the RabbitMQ consumer:", ConsoleColor.Red);
            Log(ex.Message, ConsoleColor.Red);
            return;
        }


        // Get all checks via reflection
        Check[] checks = Assembly.GetExecutingAssembly().GetTypes()
                                .Where(x => x.Namespace != null
                                        && x.Namespace.StartsWith(typeof(Check).Namespace!)
                                        && !x.IsInterface
                                        && typeof(Check).IsAssignableFrom(x))
                                .Select(x => (Check)Activator.CreateInstance(x)!).ToArray();

        Log($"Loaded {checks.Length} checks via reflection:", debug: true);
        Log(string.Join(", ", checks.Select(x => x.GetType().Name)), debug: true);

        // Run the anticheat processor
        AnticheatProcessor processor = new AnticheatProcessor(queue, checks);
        processor.Run();
    }

    private static object _lock = new object();
    
    public static void Log(string message, ConsoleColor color = ConsoleColor.Gray, bool debug = false)
    {
        // Use a lock to make the console output thread-safe
        lock (_lock)
        {
            if (debug && !_config.Debug)
                return;

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.Write($"[{DateTime.UtcNow:HH:mm:sstt}] ");
            Console.ForegroundColor = color;
            Console.WriteLine(message);
        }
    }
}