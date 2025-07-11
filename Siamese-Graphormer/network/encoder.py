import torch 
import torch.nn as nn
import torch.nn.functional as F
from .edge_attention import EdgeConditionedGraphAttention

class GraphTransformerEncoder(nn.Module):
    def __init__(self, in_channels, edge_dim, hidden_channels, out_channels, num_layers=3, num_heads=8):
        super().__init__()
        self.layers = nn.ModuleList()
        self.virtual_token = nn.Parameter(torch.randn(1, hidden_channels))

        self.input_proj = nn.Linear(in_channels, hidden_channels)

        for _ in range(num_layers):
            self.layers.append(EdgeConditionedGraphAttention(
                hidden_channels, hidden_channels, edge_dim, num_heads
            ))

        self.output_proj = nn.Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index, edge_attr, batch):
        x = self.input_proj(x)

        if edge_attr is not None and edge_attr.dim() == 1:
            edge_attr = edge_attr.unsqueeze(-1)

        batch_size = batch.max().item() + 1
        virtual = self.virtual_token.repeat(batch_size, 1)
        x = torch.cat([x, virtual], dim=0)

        virtual_index = torch.arange(x.size(0) - batch_size, x.size(0), device=x.device)

        repeated_virtual = virtual_index.repeat_interleave(batch.bincount())
        all_nodes = torch.arange(len(batch), device=x.device)
        virtual_edges = torch.stack([repeated_virtual, all_nodes], dim=0)

        new_edge_index = torch.cat([edge_index, virtual_edges], dim=1)

        reversed_edge_index = torch.stack([new_edge_index[1], new_edge_index[0]], dim=0)
        new_edge_index = torch.cat([new_edge_index, reversed_edge_index], dim=1)

        zero_virtual_edge_attr = torch.zeros(virtual_edges.size(1), edge_attr.size(-1), device=edge_attr.device)

        new_edge_attr = torch.cat([edge_attr, zero_virtual_edge_attr], dim=0)
        new_edge_attr = torch.cat([new_edge_attr, new_edge_attr.clone()], dim=0)

        batch = torch.cat([batch, torch.arange(batch_size, device=batch.device)])

        for layer in self.layers:
            x = layer(x, new_edge_index, new_edge_attr)

        return self.output_proj(x[-batch_size:])
