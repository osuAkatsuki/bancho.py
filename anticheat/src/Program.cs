using Newtonsoft.Json;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using System;
using System.Text;
using anticheat.Models;
using System.Reflection;
using anticheat.Checks;

namespace anticheat;

class Program
{
    public static void Main()
    {
        Config config = new Config();

        // Ensure the config file exists
        if (!File.Exists("config.json"))
        {
            config.Save("config.json");
            Log("Default config.json created. Set up the config file and re-run the service.", ConsoleColor.Magenta);
            return;
        }

        // Try to deserialize the config file
        try
        {
            config = Config.Load("config.json") ?? new Config();
            Log("Config loaded.", ConsoleColor.Magenta);
        }
        catch (Exception ex)
        {
            Log("An error occured while parsing the config file:", ConsoleColor.Red);
            Log(ex.Message, ConsoleColor.Red);
        }

        // Save the config file again to get rid of all old config settings
        config.Save("config.json");


        ScoreQueue queue = new ScoreQueue(config.RabbitMQHostname, config.RabbitMQPort);

        // Try to connect to the RabbitMQ broker and establish the consumer connection
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
        ICheck[] checks = Assembly.GetExecutingAssembly().GetTypes()
                                .Where(x => x.Namespace == typeof(ICheck).Namespace
                                        && !x.IsInterface
                                        &&  typeof(ICheck).IsAssignableFrom(x))
                                .Select(x => (ICheck)Activator.CreateInstance(x)!).ToArray();

        // Run the anticheat processor
        AnticheatProcessor processor = new AnticheatProcessor(queue, checks);
        processor.Run();
    }

    public static void Log(string message, ConsoleColor color = ConsoleColor.Gray)
    {
        Console.ForegroundColor = ConsoleColor.DarkGray;
        Console.Write($"[{DateTime.UtcNow:HH:mm:sstt}] ");
        Console.ForegroundColor = color;
        Console.WriteLine(message);
    }
}