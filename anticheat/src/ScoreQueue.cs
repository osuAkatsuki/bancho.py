
using System.Text;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

namespace anticheat;

internal class ScoreQueue : Queue<string>
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

    public new string Dequeue()
    {
        while(Count == 0)
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
        Enqueue(Encoding.UTF8.GetString(e.Body.ToArray()));

        Program.Log($"[RabbitMQ] A new score with ID 1 has been enqueued.", ConsoleColor.Magenta);
    }
}