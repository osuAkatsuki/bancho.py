
using System.Text;
using anticheat.Models;
using Newtonsoft.Json;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

namespace anticheat;

internal class ScoreQueue : Queue<Score>
{
    IModel? _channel = null;

    private string _hostname = "";

    private ushort _port = 0;

    public ScoreQueue(string hostname, ushort port)
    {
        _hostname = hostname;
        _port = port;
    }

    ~ScoreQueue()
    {
        _channel?.Close();
    }

    public new Score Dequeue()
    {
        while (Count == 0)
            ;

        return base.Dequeue();
    }

    public void Connect()
    {
        Program.Log($"Creating RabbitMQ connection on {_hostname}:{_port}...", ConsoleColor.Cyan);

        IConnection connection = new ConnectionFactory()
        {
            HostName = _hostname,
            Port = _port
        }.CreateConnection();

        Program.Log("RabbitMQ connection successful, creating consumer...", ConsoleColor.Cyan);

        _channel = connection.CreateModel();

        // Create a durable, non-exclusive and non-autodelete queue
        _channel.QueueDeclare("bpy.score_submission_queue", true, false, false);

        EventingBasicConsumer consumer = new EventingBasicConsumer(_channel);
        consumer.Received += Received;

        _channel.BasicConsume("bpy.score_submission_queue", true, consumer: consumer);

        Program.Log("Consumer successfully created.", ConsoleColor.Cyan);
    }

    private void Received(object? sender, BasicDeliverEventArgs e)
    {
        Program.Log($"[ScoreQueue] A new score has been received.", debug: true);

        try
        {
            string json = Encoding.UTF8.GetString(e.Body.ToArray());
            Program.Log(json);
            Score? score = JsonConvert.DeserializeObject<Score>(json);
            if (score == null)
                Program.Log($"[ScoreQueue] Null score has been received and ignored.", ConsoleColor.Magenta);
            else
            {
                Enqueue(score);
                Program.Log($"[ScoreQueue] Score with ID {score.Id} has been enqueued.", debug: true);
            }
        }
        catch (Exception ex)
        {
            Program.Log("An error occured while trying to parse the received score:", ConsoleColor.Red);
            Program.Log(ex.Message, ConsoleColor.Red);
        }
    }
}