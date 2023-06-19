# Bancho.py Helm Chart

TODO

## Generate template for reviewing

```sh
$ helm template test . --output-dir .template
```

## Testing in K8S

```sh
# Test local
$ kubectl apply -f .template --recursive --dry-run=client
# Test server-side
$ kubectl apply -f .template --recursive --dry-run=server
# Or helm install
$ helm install test . --debug --dry-run
```
